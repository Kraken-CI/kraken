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

#[derive(Debug, PartialEq, Reflection, Serialize)]
struct DateTime64(i64);

#[derive(Debug, Reflection, Serialize)]
struct LogEntryOut {
    time: DateTime64,
    message: String,
    service: String,
    host: String,
    path: String,
    lineno: u32,
    level: String,
    job: u64,
    tool: String,
    step: i8
}

async fn read_and_parse_log(buf: [u8; 65536], len: usize, mut tx: Sender<LogEntryOut>) {
    let res = serde_json::from_slice(&buf[..len]);
    if res.is_err() {
        println!("problem with parsing log '{:?}': {:?}", buf, res.unwrap_err());
        return
    }
    let le_in: Value = res.unwrap();
    //println!("{:?}", le_in);

    let ts = NaiveDateTime::parse_from_str(&le_in["@timestamp"].as_str().unwrap(), "%Y-%m-%dT%H:%M:%S%.6fZ").unwrap();
    let ts2 = ts.timestamp_nanos() / 100_000;

    let le_out = LogEntryOut{
        time: DateTime64(ts2),
        message: le_in["message"].as_str().unwrap().to_string(),
        service: le_in["service"].as_str().unwrap().to_string(),
        host: le_in["host"].as_str().unwrap().to_string(),
        path: le_in["path"].as_str().unwrap().to_string(),
        lineno: le_in["lineno"].as_i64().unwrap() as u32,
        level: le_in["level"].as_str().unwrap().to_string(),
        job: le_in.get("job").map_or(0, |v| v.as_u64().unwrap()),
        tool: le_in.get("tool").map_or("".to_string(), |v| v.as_str().unwrap().to_string()),
        step: le_in.get("step").map_or(-1, |v| v.as_i64().unwrap() as i8),
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
        insert.write(le).await?;
    }
    insert.end().await?;

    Ok(())
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
    let insert_version = r"INSERT INTO db_schema_version (id, version) VALUES (1, 1)";
    client.query(insert_version).execute().await?;

    println!("logs table created in clickhouse");
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
    println!("started clickhouse proxy");

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
