import time
import logging
import unittest
import progressbar as pg
from dicom_tools._utils import (create_progress_bar,
                                setup_logging)


class TestCreateProgressbar(unittest.TestCase):
    def setUp(self):
        self.n_steps = 10
        self.sleep = 0.02

    def task(self, seconds):
        time.sleep(seconds)

    def test_progressbar_basic(self):
        with create_progress_bar(size=self.n_steps,
                                 threaded=False) as progress:
            self.assertIsInstance(progress, pg.ProgressBar)
            for i in range(self.n_steps):
                self.task(seconds=self.sleep)
                progress.update(i)

    def test_progressbar_indefinite_length(self):
        with create_progress_bar(size=None,
                                 threaded=False) as progress:
            self.assertIsInstance(progress, pg.ProgressBar)
            for i in range(self.n_steps):
                self.task(seconds=self.sleep)
                progress.update(i)

    def test_progressbar_threaded(self):
        with create_progress_bar(size=self.n_steps,
                                 threaded=True) as progress:
            self.assertIsInstance(progress, pg.ProgressBar)
            for i in range(self.n_steps):
                self.task(seconds=self.sleep)


class TestSetupLogging(unittest.TestCase):

    def setUp(self):
        self.logger_id = "test.logger"
        self.logger = logging.getLogger(self.logger_id)

    def assert_log_level(self, level):
        LEVELS = [logging.DEBUG,
                  logging.INFO,
                  logging.WARN,
                  logging.ERROR,
                  logging.CRITICAL]
        with self.assertLogs(self.logger_id, level=level) as cm:
            for lvl in LEVELS:
                self.logger.log(lvl, "Message: %s", logging.getLevelName(lvl))
        expected_levels = [lvl for lvl in LEVELS if lvl>=level]
        self.assertEqual(len(expected_levels), len(cm.output))
        for lvl, msg in zip(expected_levels, cm.output):
            self.assertTrue(msg.startswith(logging.getLevelName(lvl)))


    def test_setup(self):
        setup_logging(verbosity=0, logger_id=self.logger_id)
        self.assert_log_level(level=logging.WARNING)
        setup_logging(verbosity=1, logger_id=self.logger_id)
        self.assert_log_level(level=logging.INFO)
        setup_logging(verbosity=2, logger_id=self.logger_id)
        self.assert_log_level(level=logging.DEBUG)
        setup_logging(verbosity=3, logger_id=self.logger_id)
        self.assert_log_level(level=logging.DEBUG)


if __name__ == "__main__":
    unittest.main(verbosity=2)
