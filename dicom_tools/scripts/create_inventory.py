#!/usr/bin/env python
import logging
import argparse
from pathlib import Path
from .._dicom_io import create_dataset_summary
from .._utils import setup_logging, ensure_out_dir, LOGGER_ID

_logger = logging.getLogger(LOGGER_ID)


def _run(args):
    root = logging.getLogger()
    setup_logging(verbosity=args.verbosity+1)
    data = create_dataset_summary(in_dir=args.in_dir,
                                  n_series_max=args.n_max)
    out_dir = Path(args.out_dir)
    if data is not None and ensure_out_dir(out_dir=out_dir):
        outpath = out_dir / "dicom_summary.csv"
        data.to_csv(outpath, index=False)
        _logger.info("Wrote summary to: %s", outpath)
        if args.verbosity > 0:
            _logger.info("Summary table:")
            print(data[["patientId", "caseId", "modality",
                        "size", "nFrames", "seriesDescription"]])


def _parse_args():
    description = ("Recursively search for DICOM data in a folder and "
                   "summarize the data in a .csv")
    formatter = argparse.RawDescriptionHelpFormatter
    parser = argparse.ArgumentParser(description=description,
                                     add_help=False,
                                     formatter_class=formatter)
    parser_group = parser.add_argument_group("Arguments")
    parser_group.add_argument("-i", "--in_dir", required=True, type=str,
                              help="Directory of a DICOM source. Required.")
    parser_group.add_argument("-o", "--out_dir", default="./out", type=str,
                              help="Output directory. Default: ./out")
    parser_group.add_argument("-v", "--verbosity", action="count", default=0,
                              help="Increase verbosity")
    parser_group.add_argument("-n", "--n-max", type=int, default=None,
                              help="Limit the number DICOM entries.")
    parser_group.add_argument("-h", "--help", action="help",
                              help="Show this help text")
    parser_group.set_defaults(func=_run)
    return parser.parse_args()


def main():
    args = _parse_args()
    args.func(args)


if __name__ == "__main__":
    main()

