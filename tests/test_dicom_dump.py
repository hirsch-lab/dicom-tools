import json
import yaml
import shutil
import logging
import tempfile
import unittest
import pydicom as dicom
from pathlib import Path

from dicom_tools._dicom_dump import (dump_to_json,
                                     dump_to_yaml,
                                     _to_dump_dict,
                                     _from_dump_dict,
                                     dump_to_json,
                                     dump_to_yaml,
                                     LOGGER_ID)


class TestDictConversions(unittest.TestCase):
    def setUp(self):
        path = dicom.data.get_testdata_file("CT_small.dcm")
        self.ds = dicom.dcmread(path)

    def test_dump(self):
        dct = _to_dump_dict(ds=self.ds)
        ds = _from_dump_dict(dct=dct)
        self.assertEqual(ds, self.ds)

    def test_dump_no_binary(self):
        # Erase binary data.
        for elm in self.ds:
            if elm.VR in ("OW", "OB"):
                elm.value = None
        dct = _to_dump_dict(ds=self.ds, skip_binary=True)
        ds = _from_dump_dict(dct, skip_binary=False)
        self.assertEqual(ds, self.ds)

        dct = _to_dump_dict(ds=self.ds, skip_binary=False)
        ds = _from_dump_dict(dct, skip_binary=True)
        self.assertEqual(ds, self.ds)

    def test_dump_no_private(self):
        self.ds.remove_private_tags()
        dct = _to_dump_dict(ds=self.ds, skip_nonstd=True)
        ds = _from_dump_dict(dct, skip_nonstd=False)
        self.assertEqual(ds, self.ds)

        dct = _to_dump_dict(ds=self.ds, skip_nonstd=False)
        ds = _from_dump_dict(dct, skip_nonstd=True)
        self.assertEqual(ds, self.ds)


class TestDumpToFile(unittest.TestCase):
    def setUp(self):
        self.out_dir = Path(tempfile.mkdtemp())
        path = dicom.data.get_testdata_file("CT_small.dcm")
        self.ds = dicom.dcmread(path)

    def tearDown(self):
        shutil.rmtree(self.out_dir)

    def test_dump_json(self):
        path = self.out_dir / "tmp.json"
        ret = dump_to_json(path=path, data=self.ds)
        self.assertTrue(ret)

        with open(path, "r") as fid:
            dct = json.load(fid)
            ds = _from_dump_dict(dct)
            self.assertEqual(ds, self.ds)

        logger = logging.getLogger(LOGGER_ID)
        with self.assertLogs(logger, logging.ERROR):
            path = self.out_dir / "tmp.xyz"
            ret = dump_to_json(path=path, data=self.ds)
            self.assertFalse(ret)
            self.assertFalse(path.is_file())

    def test_dump_yaml(self):
        path = self.out_dir / "tmp.yaml"
        ret = dump_to_yaml(path=path, data=self.ds)
        self.assertTrue(ret)

        with open(path, "r") as fid:
            dct = yaml.safe_load(fid)
            ds = _from_dump_dict(dct)
            self.assertEqual(ds, self.ds)

        logger = logging.getLogger(LOGGER_ID)
        with self.assertLogs(logger, logging.ERROR):
            path = self.out_dir / "tmp.xyz"
            ret = dump_to_yaml(path=path, data=self.ds)
            self.assertFalse(ret)
            self.assertFalse(path.is_file())
