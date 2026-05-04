"""
Test de integración: YoloPoseExtractor + LSTMFallPredictor + FallDetectionService
Usa un video real para verificar que el pipeline completo funciona correctamente.

Requiere:
    - models/yolo11x-pose.pt
    - models/fall_lstm_final.pt
    - video de prueba con una caída real
"""

import pytest
import cv2
import numpy as np
from pathlib import Path
from collections import deque

# ── Rutas ─────────────────────────────────────────────────────────────────────
YOLO_PATH  = Path("models/yolo11x-pose.pt")
LSTM_PATH  = Path("models/fall_lstm_final.pt")
VIDEO_PATH = Path("tests/videos/Office/Fall/video (15).avi")
VIDEO_NO_FALL_PATH = Path("tests/videos/Office/NFall/video (21).avi")

# Saltar tests si los archivos no existen
pytestmark = pytest.mark.skipif(
    not YOLO_PATH.exists() or not LSTM_PATH.exists() or not VIDEO_PATH.exists(),
    reason="Modelos o video no encontrados"
)


# ── Fixtures ──────────────────────────────────────────────────────────────────
@pytest.fixture(scope="module")
def yolo_extractor():
    from infrastructure.detector.yolo_pose import YoloPoseExtractor
    return YoloPoseExtractor(
        model_path=str(YOLO_PATH),
        conf=0.8,
        device="cuda:0",
    )


@pytest.fixture(scope="module")
def lstm_predictor():
    from infrastructure.detector.lstm_model import LSTMFallPredictor
    return LSTMFallPredictor(
        model_path=str(LSTM_PATH),
        device="cuda:0",
    )


@pytest.fixture(scope="module")
def fall_service(lstm_predictor):
    from domain.fall_service import FallDetectionService
    return FallDetectionService(
        module_id="test",
        min_frames=3,
        conf_lstm=0.7,
        alert_cooldown=30,
    )


# ── Tests ─────────────────────────────────────────────────────────────────────
def test_yolo_extractor_carga_correctamente(yolo_extractor):
    """Verifica que el extractor se inicializa sin errores."""
    assert yolo_extractor is not None


def test_lstm_predictor_schema_correcto(lstm_predictor):
    """Verifica que el schema del modelo es el esperado."""
    schema = lstm_predictor.schema
    assert schema.window_size == 20
    assert schema.input_size  == 68
    print(f"\nSchema: window={schema.window_size} features={schema.input_size} mode={schema.description}")


def test_yolo_detecta_persona_en_video(yolo_extractor):
    """Verifica que YOLO detecta al menos una persona en todo el video."""
    cap = cv2.VideoCapture(str(VIDEO_PATH))
    assert cap.isOpened(), f"No se pudo abrir: {VIDEO_PATH}"

    detecciones = 0
    frames_revisados = 0

    while True:
        ret, frame = cap.read()
        if not ret:
            break  # Se detiene cuando ya no hay más frames (fin del video)
            
        frames_revisados += 1
        kp = yolo_extractor.extract(frame)
        
        if kp is not None:
            detecciones += 1

    cap.release()
    print(f"\nDetecciones totales: {detecciones}/{frames_revisados} frames")
    assert detecciones > 0, f"YOLO no detectó ninguna persona en los {frames_revisados} frames del video"


def test_lstm_predice_con_keypoints_reales(yolo_extractor, lstm_predictor):
    """Verifica que el LSTM produce predicciones válidas con keypoints reales."""
    from domain.value_objects import KeypointsSequence

    cap    = cv2.VideoCapture(str(VIDEO_PATH))
    window = lstm_predictor.schema.window_size
    buffer = deque(maxlen=window)

    prediccion = None
    frames_procesados = 0

    while frames_procesados < 200:
        ret, frame = cap.read()
        if not ret:
            break
        frames_procesados += 1

        kp = yolo_extractor.extract(frame)
        if kp is not None:
            buffer.append(kp)

        if len(buffer) == window:
            sequence   = KeypointsSequence(frames=tuple(buffer))
            prediccion = lstm_predictor.predict(sequence)
            break

    cap.release()

    assert prediccion is not None, "No se pudo obtener predicción — buffer no llenó"
    assert prediccion.label in [0, 1, 2]
    assert abs(prediccion.prob_normal + prediccion.prob_fall + prediccion.prob_post - 1.0) < 1e-5
    print(
        f"\nPredicción: label={prediccion.label} "
        f"N={prediccion.prob_normal:.3f} "
        f"C={prediccion.prob_fall:.3f} "
        f"P={prediccion.prob_post:.3f}"
    )


def test_pipeline_completo_detecta_caida(yolo_extractor, lstm_predictor, fall_service):
    """
    Test de integración completo: corre el video frame a frame hasta
    que el pipeline confirme una caída o se acaben los frames.
    """
    from domain.value_objects import KeypointsSequence
    from domain.entities import FallEvent

    cap    = cv2.VideoCapture(str(VIDEO_PATH))
    window = lstm_predictor.schema.window_size
    buffer = deque(maxlen=window)

    fall_event     = None
    frame_idx      = 0
    missing_frames = 0
    MAX_MISSING    = 10

    while True:
        ret, frame = cap.read()
        if not ret:
            break
        frame_idx += 1

        kp = yolo_extractor.extract(frame)

        if kp is not None:
            missing_frames = 0
            buffer.append(kp)

            if len(buffer) == window:
                sequence   = KeypointsSequence(frames=tuple(buffer))
                prediction = lstm_predictor.predict(sequence)
                fall_event = fall_service.process(prediction, frames_buffer=[])

                if fall_event is not None:
                    print(
                        f"\nCaída confirmada en frame {frame_idx} | "
                        f"conf={fall_event.confidence:.3f}"
                    )
                    break
        else:
            missing_frames += 1
            if missing_frames > MAX_MISSING:
                buffer.clear()
                fall_service.reset()
                missing_frames = 0

    cap.release()

    assert fall_event is not None, (
        f"El pipeline no detectó ninguna caída en {frame_idx} frames. "
        f"Verifica que el video contiene una caída y que los modelos son correctos."
    )
    assert isinstance(fall_event, FallEvent)
    assert fall_event.confidence >= 0.7
    assert fall_event.module_id == "test"

def test_pipeline_no_detecta_caida_en_video_normal(yolo_extractor, lstm_predictor, fall_service):
    """
    Verifica que el pipeline NO confirma una caída en un video sin caída.
    """
    from domain.value_objects import KeypointsSequence

    # Resetear el servicio para no arrastrar estado del test anterior
    fall_service.reset()

    cap    = cv2.VideoCapture(str(VIDEO_NO_FALL_PATH))
    assert cap.isOpened(), f"No se pudo abrir: {VIDEO_NO_FALL_PATH}"

    window = lstm_predictor.schema.window_size
    buffer = deque(maxlen=window)

    fall_event     = None
    frame_idx      = 0
    missing_frames = 0
    MAX_MISSING    = 10

    while True:
        ret, frame = cap.read()
        if not ret:
            break
        frame_idx += 1

        kp = yolo_extractor.extract(frame)

        if kp is not None:
            missing_frames = 0
            buffer.append(kp)

            if len(buffer) == window:
                sequence   = KeypointsSequence(frames=tuple(buffer))
                prediction = lstm_predictor.predict(sequence)
                event      = fall_service.process(prediction, frames_buffer=[])

                if event is not None:
                    fall_event = event
                    print(
                        f"\n⚠️  Falso positivo en frame {frame_idx} | "
                        f"conf={event.confidence:.3f}"
                    )
                    break
        else:
            missing_frames += 1
            if missing_frames > MAX_MISSING:
                buffer.clear()
                fall_service.reset()
                missing_frames = 0

    cap.release()

    assert fall_event is None, (
        f"El pipeline detectó una caída falsa en frame {fall_event is not None} "
        f"en un video sin caída."
    )
    print(f"\n✅ Video sin caída procesado correctamente ({frame_idx} frames sin detección)")