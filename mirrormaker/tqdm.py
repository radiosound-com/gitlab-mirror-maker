from collections import ChainMap
from tqdm import tqdm as _tqdm

def tqdm(*args, **kwargs):
  kwargs = ChainMap(kwargs, dict(ncols=80, bar_format="{desc:14} {percentage:3.0f}% |{bar}|"))
  return _tqdm(*args, **kwargs)
