import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))
import device


def test_cpu_tier_when_no_cuda():
    t = device.choose_tier(cuda=False, vram_gb=0.0)
    assert t.device == "cpu"
    assert t.compute_type == "int8"
    assert t.model_size in ("base", "small", "distil-large-v3")


def test_big_gpu_gets_turbo_fp16():
    t = device.choose_tier(cuda=True, vram_gb=16.0)
    assert t.device == "cuda"
    assert t.model_size == "large-v3-turbo"
    assert t.compute_type in ("float16", "int8_float16")


def test_midrange_gpu_still_gets_turbo():
    # 4-6 GB cards (GTX 1650/1660, RTX 3050 laptop) must still run turbo via int8
    t = device.choose_tier(cuda=True, vram_gb=5.0)
    assert t.device == "cuda"
    assert t.model_size == "large-v3-turbo"
    assert t.compute_type == "int8_float16"


def test_small_gpu_downshifts_model():
    t = device.choose_tier(cuda=True, vram_gb=3.5)
    assert t.device == "cuda"
    assert t.model_size in ("small", "base")
    assert t.compute_type == "int8_float16"


def test_tier_is_serialisable():
    d = device.choose_tier(cuda=True, vram_gb=8.0).as_dict()
    assert set(d) == {"device", "compute_type", "model_size"}
