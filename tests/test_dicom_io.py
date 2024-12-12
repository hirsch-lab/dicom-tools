import shutil
import logging
import unittest
import tempfile
import pandas as pd
from pathlib import Path
from dicom_tools._dicom_io import (copy_from_list,
                                   copy_from_file,
                                   copy_headers,
                                   print_info,
                                   create_dataset_summary,
                                   _LOGGER_ID)
from dicom_tools._utils import setup_logging


class TestCopyFromListBase(unittest.TestCase):
    def setUp(self):
        self.in_dir = Path(tempfile.mkdtemp())
        self.out_dir = Path(tempfile.mkdtemp())
        self.n_files = 10
        for i in range(self.n_files):
            path = self.in_dir / ("file%02d" % i)
            path.touch()
        self.test_files = [f.name for f in self.in_dir.glob("file*")]

    def tearDown(self):
        shutil.rmtree(self.in_dir)
        shutil.rmtree(self.out_dir)

    def check_results(self, list_in, list_ret, out_dir=None):
        if out_dir is None:
            out_dir = self.out_dir
        self.assertIsNotNone(list_ret)
        self.assertIsInstance(list_ret, list)
        for filepath in list_ret:
            self.assertIsInstance(filepath, Path)
            self.assertTrue(filepath.is_file())
        list_copied = [str(f.relative_to(out_dir)) for f in list_ret]
        self.assertListEqual(list(list_in), list(list_copied))


class TestCopyFromList(TestCopyFromListBase):
    def test_copy_invalid_input(self):
        to_copy = self.test_files[::2]
        ret = copy_from_list(in_dir="/some/invalid/input/directory",
                             out_dir=self.out_dir,
                             to_copy=to_copy)
        self.assertIsNone(ret)

        ret = copy_from_list(in_dir=self.in_dir,
                             out_dir="/some/invalid/input/directory",
                             to_copy=to_copy)
        self.assertIsNone(ret)

    def test_partial_copy(self):
        to_copy = self.test_files[::2].copy()
        ret = copy_from_list(in_dir=self.in_dir,
                             out_dir=self.out_dir,
                             to_copy=to_copy,
                             show_progress=False)
        self.check_results(list_in=to_copy, list_ret=ret)

    def test_extended_copy_list(self):
        to_copy = self.test_files[::2].copy()
        to_copy_extended = to_copy + ["this-is-an-imaginary-file",
                                      "this-is-another-imaginary-file"]
        with self.assertLogs("dicom", level="WARNING") as cm:
            ret = copy_from_list(in_dir=self.in_dir,
                                 out_dir=self.out_dir,
                                 to_copy=to_copy_extended,
                                 raise_if_missing=False,
                                 show_progress=False)
        self.check_results(list_in=to_copy, list_ret=ret)
        self.assertEqual(len(cm.output), 2) # Show exactly two warnings.


class TestCopyFromFile(TestCopyFromListBase):
    def test_copy(self):
        to_copy = self.test_files[::2].copy()
        to_copy = pd.Series(to_copy)
        list_file = self.in_dir/"files_to_copy.csv"
        to_copy.to_csv(list_file, index=False, header=False)

        ret = copy_from_file(in_dir=self.in_dir,
                             out_dir=self.out_dir,
                             list_file=list_file,
                             show_progress=False,)
        self.check_results(list_in=to_copy, list_ret=ret)

    def test_copy_csv(self):
        to_copy = self.test_files[::2].copy()
        df = pd.concat([pd.Series(range(len(to_copy))),
                        pd.Series(to_copy)], keys=["Data", "Paths"], axis=1)
        list_file = self.in_dir/"files_to_copy.csv"
        df.to_csv(list_file)

        ret = copy_from_file(in_dir=self.in_dir,
                             out_dir=self.out_dir,
                             list_file=list_file,
                             list_column="Paths",
                             show_progress=False,)
        self.check_results(list_in=to_copy, list_ret=ret)

        with self.assertLogs("dicom", level=logging.ERROR) as cm:
            ret = copy_from_file(in_dir=self.in_dir,
                                 out_dir=self.out_dir,
                                 list_file=list_file,
                                 list_column="WrongColumn",
                                 show_progress=False,)
            self.assertIsNone(ret)

    def test_copy_flat(self):
        # In files:     <in_dir>/<file_name>
        # To copy spec: <in_dir_name>/<file_name>
        # No flat copy: <out_dir>/<in_dir_name>/<file_name>
        # Flat copy:    <out_dir>/<file_name>
        to_copy_flat = self.test_files[::2].copy()
        to_copy = [self.in_dir.name + "/" + f for f in to_copy_flat]
        to_copy = pd.Series(to_copy)
        list_file = self.in_dir/"files_to_copy.csv"
        to_copy.to_csv(list_file, index=False, header=False)

        ret = copy_from_file(in_dir=self.in_dir.parent,
                             out_dir=self.out_dir,
                             list_file=list_file,
                             flat_copy=False,
                             show_progress=False,)
        self.check_results(list_in=to_copy, list_ret=ret)

        ret = copy_from_file(in_dir=self.in_dir.parent,
                             out_dir=self.out_dir,
                             list_file=list_file,
                             flat_copy=True,
                             show_progress=False,)
        self.check_results(list_in=to_copy_flat, list_ret=ret)

    def test_copy_invalid_list_file(self):
        to_copy = self.test_files[::2].copy()
        to_copy = pd.Series(to_copy)
        list_file = self.in_dir/"files_to_copy.csv"
        to_copy.to_csv(list_file, index=False)

        ret = copy_from_file(in_dir="/some/invalid/input/directory",
                             out_dir=self.out_dir,
                             list_file=list_file,
                             show_progress=False,)
        self.assertIsNone(ret)

        ret = copy_from_file(in_dir=self.in_dir,
                             out_dir="/some/invalid/output/directory",
                             list_file=list_file,
                             show_progress=False,)
        self.assertIsNone(ret)

        ret = copy_from_file(in_dir=self.in_dir,
                             out_dir=self.out_dir,
                             list_file="/some/non-existent-file.csv",
                             show_progress=False,)
        self.assertIsNone(ret)


class TestCopyDicomHeaders(unittest.TestCase):
    def setUp(self):
        self.in_dir = Path(__file__).parent / "data"
        self.out_dir = Path(tempfile.mkdtemp())

    def tearDown(self):
        shutil.rmtree(self.out_dir)

    def test_copy_first_only(self):
        headers = copy_headers(in_dir=self.in_dir,
                               out_dir=self.out_dir,
                               glob_expr="**/*.dcm",
                               file_filter=None,
                               first_file_only=True,
                               show_progress=False,
                               skip_empty=False)
        self.assertEqual(len(headers), 3)

    def test_copy_all(self):
        headers = copy_headers(in_dir=self.in_dir,
                               out_dir=self.out_dir,
                               glob_expr="**/*.dcm",
                               file_filter=None,
                               first_file_only=False,
                               show_progress=False,
                               skip_empty=False)
        self.assertEqual(len(headers), 5)

    def test_invalid_input(self):
        headers = copy_headers(in_dir="/some/invalid/input/directory",
                               out_dir=self.out_dir)
        self.assertIsNone(headers)
        headers = copy_headers(in_dir=self.in_dir,
                               out_dir="/some/invalid/output/directory")
        self.assertIsNone(headers)


    def test_file_filter(self):
        import re
        def file_filter(filepath):
            ret = re.match(".*([0-9]+).*", filepath.parent.name)
            # Return files with odd ids.
            return (ret and int(ret.group(1))%2!=0)

        headers = copy_headers(in_dir=self.in_dir,
                               out_dir=self.out_dir,
                               glob_expr="**/*.dcm",
                               file_filter=file_filter,
                               first_file_only=True,
                               show_progress=False,
                               skip_empty=False)
        self.assertEqual(len(headers), 2)


class TestPrintInfo(unittest.TestCase):

    def setUp(self):
        self.data_dir = Path(__file__).parent / "data"
        self.case = "dataset1"
        self.path = self.data_dir / self.case
        self.assertTrue(self.path.exists())

    def test_basic_dir(self):
        # Path is a directory.
        with self.assertLogs("dicom", level=logging.INFO) as cm:
            print_info(path=self.path)
            print()
            print("INPUT: directory")
            print("OUTPUT:")
            for rec in cm.records:
                print(rec.getMessage())
            # Run print_info() with detail=True.
            print_info(path=self.path, detailed=True)

    def test_basic_file(self):
        # Path is a directory.
        files = list(sorted(self.path.glob("*.dcm")))
        self.assertTrue(len(files)>0)
        filepath = files[0]
        with self.assertLogs("dicom", level=logging.INFO) as cm:
            print_info(path=filepath)
            print()
            print("INPUT: file")
            print("OUTPUT:")
            for rec in cm.records:
                print(rec.getMessage())
            print_info(path=filepath, detailed=True)

    def test_invalid_input(self):
        with self.assertLogs("dicom", level=logging.ERROR) as cm:
            print_info(path="this/is/some/invalid/path")
            self.assertEqual(len(cm.output), 1)
            log_record = cm.records[0]
            log_message = log_record.getMessage()
            text = "File or folder does not exist"
            self.assertTrue(log_message.startswith(text))
        with tempfile.TemporaryDirectory() as some_empty_folder:
            with self.assertLogs("dicom", level=logging.ERROR) as cm:
                print_info(path=some_empty_folder)
                self.assertEqual(len(cm.output), 1)
                log_record = cm.records[0]
                log_message = log_record.getMessage()
                self.assertTrue(log_message.startswith("No DICOM files found"))
            with self.assertLogs("dicom", level=logging.ERROR) as cm:
                # Create a non-DICOM file
                some_non_dicom_file = Path(some_empty_folder) / "empty.txt"
                some_non_dicom_file.touch()
                print_info(path=some_non_dicom_file)
                self.assertEqual(len(cm.output), 1)
                log_record = cm.records[0]
                log_message = log_record.getMessage()
                self.assertTrue(log_message.startswith("Expecting a DICOM"))


class TestCreateDatasetSummary(unittest.TestCase):

    def setUp(self):
        self.data_dir = Path(__file__).parent / "data"
        self.out_dir = Path(tempfile.mkdtemp())

    def test_basic(self):
        summary = create_dataset_summary(in_dir=self.data_dir)
        self.assertEqual(len(summary), 3)

    def test_basic(self):
        summary = create_dataset_summary(in_dir=self.data_dir,
                                         n_series_max=2)
        self.assertEqual(len(summary), 2)


class TestExtendedCreateDatasetSummary(unittest.TestCase):

    def setUp(self):
        self.data_dir = Path(__file__).parent / "data"
        self.out_dir = Path(tempfile.mkdtemp())

    def test_basic(self):
        summary = create_dataset_summary(in_dir=self.data_dir,
                                         extra_tags=["Manufacturer", "ManufacturerModelName"])
        self.assertTrue("manufacturer" in summary.columns)
        self.assertTrue("manufacturerModelName" in summary)


if __name__ == "__main__":
    unittest.main(verbosity=2)
