use std::io;
use std::env;

use tokio::net::UdpSocket;
use tokio::sync::mpsc;
use tokio::sync::mpsc::{Sender, Receiver};
use tokio::time::{timeout, delay_for, Duration};
use serde::{Deserialize, Serialize};
use serde_json::{Value};
use clickhouse::{error::Result, Client, Reflection};
use chrono::NaiveDateTime;

#[derive(Debug, Deserialize)]
struct LogEntryIn {
    time: String,
    message: String,
    service: String,
    origin: String,
    host: String,
    level: String,
    job: u32,
    tool: String,
    step: i8
}

#[derive(Debug, PartialEq, Reflection, Serialize, Copy, Clone)]
struct DateTime64(i64);

#[derive(Debug, Reflection, Serialize)]
struct LogEntryOut {
    time: DateTime64,
    seq: u16,
    message: String,
    service: String,
    host: String,
    path: String,
    lineno: u32,
    level: String,
    branch: u64,
    flow_kind: u8,
    flow: u64,
    run: u64,
    job: u64,
    tool: String,
    step: i8,
    agent: u64,
}

const KRAKEN_VERSION: &str = env!("KRAKEN_VERSION");

async fn read_and_parse_log(buf: [u8; 65536], len: usize, mut tx: Sender<LogEntryOut>) {
    let res = serde_json::from_slice(&buf[..len]);
    if res.is_err() {
        println!("problem with parsing log '{:?}': {:?}", buf, res.unwrap_err());
        return
    }
    let le_in: Value = res.unwrap();
    // println!("{:?}", le_in);

    let ts = NaiveDateTime::parse_from_str(&le_in["@timestamp"].as_str().unwrap(), "%Y-%m-%dT%H:%M:%S%.6fZ").unwrap();
    let ts2 = ts.timestamp_nanos() / 100_000;

    let service = match le_in["service"].as_str() {
        Some(s) => s.to_string(),
        None => {
            println!("warn: no service {:?}", le_in["message"].as_str().unwrap().to_string());
            "unknown".to_string()
        }
    };

    let le_out = LogEntryOut{
        time: DateTime64(ts2),
        seq: 0,
        message: le_in["message"].as_str().unwrap().to_string(),
        service: service,
        host: le_in["host"].as_str().unwrap().to_string(),
        path: le_in["path"].as_str().unwrap().to_string(),
        lineno: le_in["lineno"].as_i64().unwrap() as u32,
        level: le_in["level"].as_str().unwrap().to_string(),
        branch: le_in.get("branch").map_or(0, |v| v.as_u64().unwrap()),
        flow_kind: le_in.get("flow_kind").map_or(0, |v| v.as_u64().unwrap() as u8),
        flow: le_in.get("flow").map_or(0, |v| v.as_u64().unwrap()),
        run: le_in.get("run").map_or(0, |v| v.as_u64().unwrap()),
        job: le_in.get("job").map_or(0, |v| v.as_u64().unwrap()),
        tool: le_in.get("tool").map_or("".to_string(), |v| v.as_str().unwrap().to_string()),
        step: le_in.get("step").map_or(-1, |v| v.as_i64().unwrap() as i8),
        agent: le_in.get("agent").map_or(0, |v| v.as_u64().unwrap()),
    };

    let res = tx.send(le_out).await;
    match res {
        Ok(_) => {},
        Err(err) => { println!("problem with sending over channel: {:?}", err); }
    }
}

async fn store_logs_batch(client: &Client, batch: &Vec<LogEntryOut>) -> Result<()> {
    println!("storing batch {:?}", batch.len());

    let mut insert = client.insert("logs")?;
    for le in batch.iter() {
        for (idx, line) in le.message.lines().enumerate() {
            let le2 = LogEntryOut{
                time: le.time.clone(),
                seq: idx as u16,
                message: line.to_string(),
                service: le.service.clone(),
                host: le.host.clone(),
                path: le.path.clone(),
                lineno: le.lineno,
                level: le.level.clone(),
                branch: le.branch,
                flow_kind: le.flow_kind,
                flow: le.flow,
                run: le.run,
                job: le.job,
                tool: le.tool.clone(),
                step: le.step,
                agent: le.agent,
            };
            // println!("msg {:?} {:?}", idx, le2.message);
            insert.write(&le2).await?;
        }
    }
    insert.end().await?;

    Ok(())
}

#[derive(Reflection, Deserialize, Debug)]
struct VersionRow<> {
    version: u32
}

async fn store_logs(rx: &mut Receiver<LogEntryOut>) -> Result<()> {
    let ch_url = env::var("KRAKEN_CLICKHOUSE_URL").unwrap();
    let client = Client::default().with_url(ch_url);

    // create logs table
    let create_logs_tbl = r"CREATE TABLE IF NOT EXISTS logs(
        `time` DateTime64(4),
        `message` String,
        `service` String,
        `host` String,
        `path` String,
        `lineno` UInt32,
        `level` String,
        `job` UInt64,
        `tool` String,
        `step` Int8)
        ENGINE = MergeTree
        PARTITION BY toYearWeek(time, 9)
        ORDER BY time";
    client.query(create_logs_tbl).execute().await?;

    // prepare db schema version table
    let create_db_schema_version_tbl = r"CREATE TABLE IF NOT EXISTS db_schema_version(
        `id` UInt32,
        `version` UInt32)
        ENGINE = ReplacingMergeTree
        ORDER BY id";
    client.query(create_db_schema_version_tbl).execute().await?;

    // get latest version
    let mut db_version = 1 as u32;
    let mut cursor = client.query("SELECT version FROM db_schema_version").fetch::<VersionRow<>>()?;
    while let Some(row) = cursor.next().await? {
        println!("{:?}", row);
        if row.version > db_version {
            db_version = row.version;
        }
    }

    // migration to version 2
    if db_version < 2 {
        let cmd = r"ALTER TABLE logs ADD COLUMN seq UInt16 AFTER time, MODIFY ORDER BY (time, seq)";
        client.query(cmd).execute().await?;
        db_version += 1;
    }

    // migration to version 3
    if db_version < 3 {
        let cmd = r"ALTER TABLE logs MODIFY TTL toDateTime(time) + INTERVAL 6 MONTH";
        client.query(cmd).execute().await?;
        db_version += 1;
    }

    // migration to version 4
    if db_version < 4 {
        let cmd = r"ALTER TABLE logs ADD COLUMN run UInt64 AFTER level, ADD COLUMN flow UInt64 AFTER level, ADD COLUMN branch UInt64 AFTER level";
        client.query(cmd).execute().await?;
        db_version += 1;
    }

    // migration to version 5
    if db_version < 5 {
        let cmd1 = r"ALTER TABLE logs ADD INDEX job_ix job TYPE set(100) GRANULARITY 2";
        client.query(cmd1).execute().await?;
        let cmd2 = r"ALTER TABLE logs MATERIALIZE INDEX job_ix";
        client.query(cmd2).execute().await?;
        db_version += 1;
    }

    // migration to version 6
    if db_version < 6 {
        let cmd = r"ALTER TABLE logs ADD COLUMN flow_kind UInt8 AFTER branch";
        client.query(cmd).execute().await?;
        db_version += 1;
    }

    // migration to version 7
    if db_version < 7 {
        let cmd = r"ALTER TABLE logs ADD COLUMN agent UInt64 AFTER step";
        client.query(cmd).execute().await?;
        db_version += 1;
    }

    // migration to version 8
    if db_version < 8 {
        let fields: [&str; 4] = ["branch", "flow", "run", "agent"];
        for f in &fields {
            let cmd1 = format!(r"ALTER TABLE logs ADD INDEX {f}_ix {f} TYPE set(100) GRANULARITY 2");
            client.query(&cmd1).execute().await?;
            let cmd2 = format!(r"ALTER TABLE logs MATERIALIZE INDEX {f}_ix");
            client.query(&cmd2).execute().await?;
        }
        db_version += 1;
    }

    // store latest version
    let insert_version = r"INSERT INTO db_schema_version (id, version) VALUES (1, ?)";
    client.query(insert_version).bind(db_version).execute().await?;

    println!("logs table created or updated in clickhouse, now db version {:?}", db_version);
    println!("waiting for logs to store");

    let mut batch = Vec::with_capacity(100);

    loop {
        match timeout(Duration::from_secs(1), rx.recv()).await {
            Ok(Some(le)) => {
                //println!("{:?}", le);
                batch.push(le);
                if batch.len() == 100 {
                    let res = store_logs_batch(&client, &batch).await;
                    if res.is_err() {
                        println!("problem with storing logs: {:?}", res.unwrap_err())
                    }
                    batch.clear();
                }
            }
            Ok(None) => {
                if batch.len() > 0 {
                    let res = store_logs_batch(&client, &batch).await;
                    if res.is_err() {
                        println!("problem with storing logs: {:?}", res.unwrap_err())
                    }
                    batch.clear();
                }
            }
            Err(_) => {
                if batch.len() > 0 {
                    let res = store_logs_batch(&client, &batch).await;
                    if res.is_err() {
                        println!("problem with storing logs: {:?}", res.unwrap_err())
                    }
                    batch.clear();
                }
            }
        }
    }
}


#[tokio::main]
async fn main() -> io::Result<()> {
    println!("started clickhouse proxy, version {:?}", KRAKEN_VERSION);

    let ch_url = env::var("KRAKEN_CLICKHOUSE_URL");
    match ch_url {
        Ok(url) => println!("Clickhouse address: {:?}", url),
        Err(_) => {
            println!("Error: environment variable KRAKEN_CLICKHOUSE_URL is not set, exiting.");
            std::process::exit(1);
        }
    }

    let (tx, mut rx) = mpsc::channel(32);

    tokio::spawn(async move {
        loop {
            let res = store_logs(&mut rx).await;
            println!("STORE LOGS ERR: {:?}", res);
            delay_for(Duration::from_secs(2)).await;
        }
    });

    let mut sock = UdpSocket::bind("0.0.0.0:9001").await?;
    loop {
        let mut buf = [0; 65536];
        let (len, _addr) = sock.recv_from(&mut buf).await?;

        let tx2 = tx.clone();
        tokio::spawn(async move {
            read_and_parse_log(buf, len, tx2).await;
        });
    }
}
