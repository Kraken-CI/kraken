import tempfile
from pathlib import Path
from unittest.mock import patch

from kraken.agent import kraken_artifacts



def test_run_artifacts_upload():
    collected_artifacts = []
    def report_artifact(art):
        collected_artifacts.append(art)

    with tempfile.TemporaryDirectory() as tmpdirname:
        tmpdir = Path(tmpdirname)

        # prepare files to upload
        f1 = tmpdir / 'a.txt'
        f1.touch()
        d1 = tmpdir / 'd1'
        d1.mkdir()
        f2 = d1 / 'b.txt'
        f2.touch()

        step = dict(
            flow_id=123,
            run_id=456,
            minio_addr='minio:9000',
            minio_bucket='00000015',
            minio_access_key='123',
            minio_secret_key='321',
            cwd=tmpdirname,
            source=tmpdirname + '/**',
            destination='/'
        )

        with patch('minio.Minio.bucket_exists', return_value=True) as be, patch('minio.Minio.fput_object') as fput:
            res, msg = kraken_artifacts.run_artifacts(step, report_artifact=report_artifact)
            assert res == 0

            assert be.called

            fput.assert_any_call('00000015', '123/456/a.txt', str(f1))
            fput.assert_any_call('00000015', '123/456/d1/b.txt', str(f2))

            a1 = dict(path='a.txt', size=0)
            a2 = dict(path='d1/b.txt', size=0)
            assert a1 in collected_artifacts
            assert a2 in collected_artifacts


class Obj:
    pass

def test_run_artifacts_download():
    with tempfile.TemporaryDirectory() as tmpdirname:

        step = dict(
            flow_id=123,
            run_id=456,
            minio_addr='minio:9000',
            minio_bucket='00000015',
            minio_access_key='123',
            minio_secret_key='321',
            action='download',
            cwd=tmpdirname,
            source='a1.txt',
            destination='.'
        )

        with patch('minio.Minio.bucket_exists', return_value=True) as be, \
             patch('minio.Minio.fget_object') as fget, \
             patch('minio.Minio.list_objects') as mlist:
            o = Obj()
            o.object_name = '123/455/'
            o.is_dir = True
            mlist.return_value = [o]

            kraken_artifacts.run_artifacts(step, report_artifact=None)

            assert be.called

            fget.assert_any_call('00000015', '123/455/a1.txt', tmpdirname + '/a1.txt')
