import logging
from pathlib import Path
import progressbar as pg # Package: progressbar2

LOGGER_ID = "dicom"
_logger = logging.getLogger(LOGGER_ID)

# Run static type checking with the following command:
# mypy _utils.py --ignore-missing-imports --allow-redefinition
from typing import TypeVar, Optional, List, Callable
PathLike = TypeVar("PathLike", str, Path)
OptionalPathList = Optional[List[Path]]
OptionalFilter = Optional[Callable[[PathLike], bool]]


def check_in_dir(in_dir: PathLike) -> bool:
    in_dir = Path(in_dir)
    if not in_dir.is_dir():
        _logger.error("Input directory does not exist: %s", in_dir)
        return False
    else:
        return True


def ensure_out_dir(out_dir: PathLike, raise_error: bool=False) -> bool:
    out_dir = Path(out_dir)
    if not out_dir.is_dir():
        _logger.debug("Creating target directory: %s...", out_dir)
        try:
            out_dir.mkdir(parents=True, exist_ok=True)
        except (PermissionError, OSError) as ex:
            msg = "Caught an exception when creating the target directory: %s"
            _logger.error(msg, out_dir)
            _logger.error(str(ex))
            # For a stacktrace:
            #_logger.exception("Exception:")
            #_logger.error(msg)
            if raise_error:
                raise  # pragma: no cover
    return out_dir.is_dir()


def create_progress_bar(size: Optional[int]=None,
                        label: str="Processing...",
                        threaded: bool=False,
                        enabled: bool=True) -> pg.ProgressBar:
    widgets = []
    if label:
        widgets.append(pg.FormatLabel("%-5s:" % label))
        widgets.append(" ")
    if size is not None and size>0:
        digits = len(str(size))
        fmt_counter = f"%(value){digits}d/{size}"
        widgets.append(pg.Bar())
        widgets.append(" ")
        widgets.append(pg.Counter(fmt_counter))
        widgets.append(" (")
        widgets.append(pg.Percentage())
        widgets.append(")")
    else:
        widgets.append(pg.BouncingBar())
    ProgressBarType: pg.ProgressBar = pg.ProgressBar if enabled else pg.NullBar
    if threaded and enabled:
        from threading import Timer
        class RepeatTimer(Timer):
            def run(self):
                while not self.finished.wait(self.interval):
                    self.function(*self.args, **self.kwargs)
        class ThreadedProgressBar(ProgressBarType):
            def __init__(self, *args, **kwargs):
                super().__init__(*args, **kwargs)
                self.timer = RepeatTimer(interval=0.05,
                                         function=self.update)
                try:
                    self.timer.daemon = True
                except AttributeError:
                    # Deprecated since Python 3.10
                    self.timer.setDaemon(True)
            def run(self):
                while not self.finished.wait(self.interval):
                    self.function(*self.args, **self.kwargs)
            def start(self, *args, **kwargs):
                ret = super().start(*args, **kwargs)
                self.timer.start()
                return ret
            def finish(self, *args, **kwargs):
                self.timer.cancel()
                return super().finish(*args, **kwargs)
        ProgressBarType = ThreadedProgressBar

    progress = ProgressBarType(max_value=size,
                               widgets=widgets,
                               poll_interval=0.02)
    return progress


def setup_logging(verbosity: Optional[int]=None,
                  logger_id: Optional[str]=None) -> None:
    """
    Set verbosity of internal and relevant external loggers.

    If no logger_id is provided, the verbosity is applied to the root logger.
    """
    logging.addLevelName(logging.DEBUG,   "DEBUG")
    logging.addLevelName(logging.INFO,    "INFO")
    logging.addLevelName(logging.WARNING, "WARN")
    logging.addLevelName(logging.ERROR,   "ERROR")
    level = logging.WARNING
    level_ext = logging.ERROR
    verbosity = 0 if verbosity is None else verbosity
    if verbosity == 1:
        level = logging.INFO
    elif verbosity == 2:
        level = logging.DEBUG
        level_ext = logging.WARNING
    elif verbosity>= 3:
        level = logging.DEBUG
        level_ext = logging.DEBUG
    for name in ["pydicom", ]:
        logger = logging.getLogger(name)
        logger.setLevel(level_ext)
    fmt = "%(levelname)-5s: [%(name)-10s] %(message)s"
    fmt = "%(levelname)-5s: %(message)s"
    logging.basicConfig(level=logging.WARNING, format=fmt)
    logger = logging.getLogger(logger_id)
    logger.setLevel(level)
