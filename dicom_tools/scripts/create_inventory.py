#!/usr/bin/env python
import logging
import argparse
from pathlib import Path
from .._dicom_io import create_dataset_summary
from .._utils import setup_logging, ensure_out_dir, LOGGER_ID

_logger = logging.getLogger(LOGGER_ID)
_out_path = "./dicom_summary.csv"


def _run(args):
    root = logging.getLogger()
    setup_logging(verbosity=args.verbosity+1)
    data = create_dataset_summary(in_dir=args.in_dir,
                                  n_series_max=args.n_max,
                                  glob_expr=args.glob,
                                  reg_expr=args.regex,
                                  extra_keys=args.extra_keys)
    out_path = Path(args.out_path)
    if data is not None and ensure_out_dir(out_dir=out_path.parent):
        data.to_csv(out_path, index=False)
        _logger.info("Wrote summary to: %s", out_path)
        if args.verbosity > 0:
            _logger.info("Summary table:")
            print(data[["patientId", "caseId", "modality",
                        "size", "nFrames", "seriesDescription"]])


def _parse_args():
    description = ("Recursively search for DICOM data in a folder and "
                   "summarize the data in a .csv")
    formatter = argparse.RawTextHelpFormatter
    parser = argparse.ArgumentParser(description=description,
                                     add_help=False,
                                     formatter_class=formatter)
    parser_group = parser.add_argument_group("Arguments")
    parser_group.add_argument("-i", "--in-dir", required=True, type=str,
                              help="Directory of a DICOM source. Required.")
    parser_group.add_argument("-o", "--out-path", default=_out_path, type=str,
                              help="Path to output file. Default: " + _out_path)
    parser_group.add_argument("-v", "--verbosity", action="count", default=0,
                              help="Increase verbosity")
    parser_group.add_argument("-g", "--glob", type=str, default=None,
                              help=("Glob filter expression.\n"
                                    "Example: --glob='patID/**/*.dcm'.\n"
                                    "See also: --regex"))
    parser_group.add_argument("-r", "--regex", type=str, default=None,
                              help=("Filter files that match a regexp.\n"
                                    "- If both --glob and --regex are set:\n"
                                    "  --glob is evaluated first, then --regex\n"
                                    "- If neither --glob nor --regex are set:\n"
                                    "  Default choice is --glob=**/*.dcm"))
    parser_group.add_argument("-e", "--extra-keys", nargs="+", type=str,
                              default=None, help="Extra DICOM keys to extract.")
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

