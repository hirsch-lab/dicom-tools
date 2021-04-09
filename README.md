# dicom-tools

[![License](https://img.shields.io/pypi/l/roc-utils)](https://github.com/hirsch-lab/dicom-tools/blob/main/LICENSE)
[![Python 3.6+](https://img.shields.io/badge/python-3.6+-blue.svg)](https://www.python.org/downloads/)

Collection of command line utilities to operate on DICOM data.

## Setup


The tools are written entirely in Python (version >=3.6)

Download the repository and install required packages:

```bash
git clone "https://github.com/hirsch-lab/dicom-tools.git"
cd dicom-tools
python -m pip install -r "requirements.txt"
```

Build and install the package from source:

```bash
# Build package
python setup.py sdist
# Install
python -m pip install "dist/dicom-tools*.tar.gz"
```

This installs the below command-line tools. 

```bash
dicom-copy-from-list -h
dicom-copy-headers -h
dicom-inventory -h
dicom-print-info -h
```

Note: it is possible to run the command-line utilities without installing the package. 

```bash
# In the root directory of the project
python -m "dicom_tools.scripts.copy_from_list" -h
python -m "dicom_tools.scripts.copy_headers" -h
# ...
```


## Functionality

The following command-line utilities are availble after installing the dicom-tools package.

**`dicom-copy-from-list`**

- Implemented in [`dicom_tools.scripts.copy_from_list`](https://github.com/hirsch-lab/dicom-tools/blob/main/dicom_tools/scripts/copy_from_list.py)
- Copy a subset of DICOM folders as specified in an input list.


**`dicom-copy-headers`**

- Implemented in [`dicom_tools.scripts.copy_headers`](https://github.com/hirsch-lab/dicom-tools/blob/main/dicom_tools/scripts/copy_headers.py)
- Copy DICOM files without pixel data. This is useful if the image repository is too heavy.

**`dicom-inventory`**

- Implemented in [`dicom_tools.scripts.create_inventory.py `](https://github.com/hirsch-lab/dicom-tools/blob/main/dicom_tools/scripts/create_inventory.py)
- Create a .csv file with summary information about all DICOM series in folder

**`dicom-print-info`**

- Implemented in [`dicom_tools.scripts.print_info`](https://github.com/hirsch-lab/dicom-tools/blob/main/dicom_tools/scripts/print_info.py)
- Print header info of a DICOM file 


### Sample calls

```bash
# Copy from a list of content
dicom-copy-from-list --in-dir "path/to/dicom/repository" \
                     --out-dir "path/to/output/" \
                     --list-file "path/to/list.csv"

# Copy headers.
dicom-copy-headers --in-dir "path/to/dicom/repository" \
                   --out-dir "path/to/output/"

# Print info about a DICOM file.
dicom-print-info --in-file "path/to/dicom/file-or-folder"
dicom-print-info --in-file "path/to/dicom/file-or-folder" --all

# Create a summary of a DICOM repository.
dicom-inventory --in-dir "path/to/dicom/repository" -v
```


## Development

Run the unitests with [pytest](https://docs.pytest.org/en/stable/). See also the file `.coveragerc` for the settings of the code coverage analysis

```bash
pytest
# To see print statements, use the -s flag
pytest -s 
# To see nicely formatted live logs, use the flag `--log-cli-level`
# Note: Don't confuse failing tests with error-logs. 
pytest --log-cli-level="info"
# To assess code coverage (requires package pytest-cov)
pytest --cov \
       --cov-config="./.coveragerc" \
       --cov-report=html
```

The package uses type hints. For a static type check, install [mypy](http://mypy-lang.org/) and run the following command:

```bash
mypy "dicom_tools" --ignore-missing-imports --allow-redefinition
```

## Further reading

[DICOM standard](https://www.dicomstandard.org/current)  
[DICOM dictionary browser](https://dicom.innolitics.com/ciods)  
[Pydicom](https://pydicom.github.io/) ([docs](https://pydicom.github.io/pydicom/stable/), [api docs](https://dicomweb-client.readthedocs.io/en/latest/  
[Python type checking](https://realpython.com/python-type-checking)