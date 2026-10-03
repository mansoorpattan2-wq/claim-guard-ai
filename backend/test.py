import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).parent/'vendor'))
import pytest
raise SystemExit(pytest.main([str(Path(__file__).parent/'tests'),'-q']))
