#!/usr/bin/env python
import logging
import argparse
from .._dicom_io import print_info
from .._utils import setup_logging


def _run(args):
    root = logging.getLogger()
    setup_logging(verbosity=args.verbosity+1)
    print_info(path=args.in_file,
               detailed=args.all)


def _parse_args():
    description = ("Print basic or detailed info about a DICOM file in "
                   "the console.")
    formatter = argparse.RawDescriptionHelpFormatter
    parser = argparse.ArgumentParser(description=description,
                                     add_help=False,
                                     formatter_class=formatter)
    parser_group = parser.add_argument_group("Arguments")
    parser_group.add_argument("-i", "--in_file", required=True,
                              help=("A DICOM file or directory of containing "
                                    "a DICOM series. Required."))
    parser_group.add_argument("-v", "--verbosity", action="count", default=0,
                              help="Increase verbosity")
    parser_group.add_argument("-a", "--all", action="store_true",
                              help=("Print all available DICOM fields."))
    parser_group.add_argument("-h", "--help", action="help",
                              help="Show this help text")
    parser_group.set_defaults(func=_run)
    return parser.parse_args()


def main():
    args = _parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
