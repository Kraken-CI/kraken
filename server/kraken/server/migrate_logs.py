import os
from urllib.parse import urlparse

from elasticsearch import Elasticsearch
import clickhouse_driver
import dateutil.parser

def _get_logs_batch_from_es():
    es_server = os.environ.get('KRAKEN_ELASTICSEARCH_URL')
    es = Elasticsearch(es_server)

    query = {"query": {"bool": {"must": []}}}
    query["size"] = 10000
    query["sort"] = [{"@timestamp": {"order": "asc"}}, {"_id": "desc"}]

    count = 1
    search_after = None
    while True:
        if search_after:
            ts, _id = search_after
            query['search_after'] = [int(ts), _id]

        try:
            res = es.search(index="logstash*", body=query)
        except:
            # try one more time
            res = es.search(index="logstash*", body=query)

        logs = []
        for hit in res['hits']['hits']:
            l = hit[u'_source']
            entry = dict(time=dateutil.parser.parse(l[u'@timestamp']),
                         message=l['message'],
                         service=l['service'] if u'service' in l else "",
                         host=l['host'],
                         level=l['level'].lower()[:4] if u'level' in l else "info",
                         job=l['job'] if 'job' in l else 0,
                         tool=l['tool'] if 'tool' in l else "",
                         step=l['step'] if 'step' in l else -1)
            logs.append(entry)

        if len(logs) == 0:
            break

        yield logs

        search_after = res['hits']['hits'][-1]['sort']
        #total = res['hits']['total']['value']


def main():
    print('started migrating logs')

    ch_url = os.environ.get('KRAKEN_CLICKHOUSE_URL')
    o = urlparse(ch_url)
    ch = clickhouse_driver.Client(host=o.hostname)

    for batch in _get_logs_batch_from_es():
        print(len(batch))
        ch.execute('INSERT INTO logs (time,message,service,host,level,job,tool,step) VALUES', batch)


if __name__ == '__main__':
    main()
