# tests/test_domain.py

import pytest
import numpy as np
from domain.value_objects import FeatureSchema

def test_feature_schema_valida_correctamente():
    schema = FeatureSchema(window_size=20, input_size=68, description="coco_xy_vel")
    frames = tuple([np.zeros(68)] * 20)
    schema.validate(frames)  # no debe lanzar nada

def test_feature_schema_falla_ventana_incorrecta():
    schema = FeatureSchema(window_size=20, input_size=68, description="coco_xy_vel")
    frames = tuple([np.zeros(68)] * 15)  # solo 15 frames
    with pytest.raises(ValueError):
        schema.validate(frames)  # debe lanzar ValueError

# --- FeatureSchema ---
def test_feature_schema_falla_features_incorrectas():
    schema = FeatureSchema(window_size=20, input_size=68, description="coco_xy_vel")
    frames = tuple([np.zeros(50)] * 20)  # 50 features en vez de 68
    with pytest.raises(ValueError):
        schema.validate(frames)

# --- Keypoints ---
def test_keypoints_se_crea_correctamente():
    from domain.value_objects import Keypoints
    arr = np.zeros(34, dtype=np.float32)
    kp  = Keypoints.from_array(arr)
    assert len(kp.values) == 34

def test_keypoints_falla_con_tamano_incorrecto():
    from domain.value_objects import Keypoints
    with pytest.raises(ValueError):
        Keypoints(values=tuple([0.0] * 20))  # solo 20 valores

# --- FallDetectionService ---
def test_fall_service_no_confirma_sin_min_frames():
    from domain.fall_service import FallDetectionService
    from domain.entities import FallPrediction
    service = FallDetectionService(module_id="test", min_frames=3, conf_lstm=0.7)
    pred = FallPrediction(label=1, prob_normal=0.1, prob_fall=0.8, prob_post=0.1)
    result = service.process(pred, frames_buffer=[])
    assert result is None  # solo 1 frame, no alcanza min_frames

def test_fall_service_confirma_caida():
    from domain.fall_service import FallDetectionService
    from domain.entities import FallPrediction
    service = FallDetectionService(module_id="test", min_frames=3, conf_lstm=0.7)
    pred = FallPrediction(label=1, prob_normal=0.1, prob_fall=0.8, prob_post=0.1)
    service.process(pred, frames_buffer=[])
    service.process(pred, frames_buffer=[])
    result = service.process(pred, frames_buffer=[])  # tercer frame
    assert result is not None
    assert result.confidence >= 0.7