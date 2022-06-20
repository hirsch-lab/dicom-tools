import logging
import argparse
import os

from pydicom import dcmread
from pathlib import Path
from dicom_tools._utils import setup_logging
from dicom_tools._dicom_dump import dump_to_yaml
from dicom_tools._conversion import dicom2nifti_dir

LOGGER_ID = "nifti"
_logger = logging.getLogger(LOGGER_ID)

def _run(args):
    setup_logging(verbosity=args.verbosity + 1)
    dcm2nii_logger = logging.getLogger("dicom2nifti")
    dcm2nii_logger.setLevel(logging.ERROR)
    if args.create_attribute_file:
        files = sorted(os.listdir(Path(args.in_dir)))
        for f in files:
            try:
                ds = dcmread(os.path.join(Path(args.in_dir), f))
                _logger.info("The file {} could be read by pydicom".format(f))
                ret = dump_to_yaml(path= args.create_attribute_file, data=ds)
                if ret:
                    _logger.info("File written: %s", args.create_attribute_file)
                break
            except:
                _logger.error("The file {} could not be read by pydicom".format(f))
        exit(1)

    dicom2nifti_dir(in_dir=args.in_dir,
                    out_dir=args.out_dir,
                    compress=args.compression,
                    reorient=args.reorient,
                    flat=args.flat,
                    override=args.force,
                    skip_existing=not args.force)


def _parse_args():
    description = ("Convert a stack of DICOM images into a nifti.\n"
                   "The dicom files however need to hold information about\n"
                   "slice-localization and have to exceed the count of 4.\n"
                   "Furthermore is this function only applicable on 3D data sets.\n\n")
    formatter = argparse.RawTextHelpFormatter
    parser = argparse.ArgumentParser(description=description,
                                     add_help=False,
                                     formatter_class=formatter)

    # General
    group = parser.add_argument_group("General")
    group.add_argument("-h", "--help", action="help",
                       help="Show this help text")
    group.add_argument("-v", "--verbosity", action="count", default=0,
                       help="Increase verbosity")

    # IO
    group = parser.add_argument_group("IO")
    group.add_argument("-i", "--in-dir", required=True,
                       help=("A folder containing the images."))
    group.add_argument("-o", "--out-dir", default="./out", type=str,
                       help=("Output directory. Default: ./out"))

    group.add_argument("-f", "--force", action="store_true",
                       help="Force writing of output files.")
    group.add_argument("--flat", action="store_true",
                       help="Flatten the input directory.")

    # DICOM
    group = parser.add_argument_group(("DICOM"))
    group.add_argument("--create-attribute-file", default=None, type=str,
                       nargs="?", const="./out/current_dicom_attributes.yaml",
                       help="Creates an attribute file of the first dicom-file\n"
                            "inside the given folder.")

    # NIFTI
    group = parser.add_argument_group("NIFTI")
    group.add_argument("-c", "--compression", default=True, type=bool,
                       help=("Compression to nii.gz. Default: True"))
    group.add_argument("-r", "--reorient", default=False, type=bool,
                       help=("Reorientation of DICOM data to LAS orientation. Default: False"))


    group.set_defaults(func=_run)
    return parser.parse_args()



def main():
    args = _parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
