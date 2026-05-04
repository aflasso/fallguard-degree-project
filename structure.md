fall_detection_module/
├── domain/
│   ├── entities.py
│   └── fall_service.py
│
├── application/
│   ├── ports/
│   │   ├── fall_predictor.py
│   │   ├── keypoint_extractor.py
│   │   ├── clip_storage.py
│   │   └── alert_sender.py
│   └── use_cases/
│       ├── detect_fall.py
│       ├── send_alert.py
│       └── manage_camera.py
│
├── infrastructure/
│   ├── detector/
│   │   ├── yolo_pose.py
│   │   └── lstm_model.py
│   ├── video/
│   │   ├── opencv_camera.py
│   │   └── clip_recorder.py
│   ├── comms/
│   │   ├── ws_client.py
│   │   └── s3_uploader.py
│   └── storage/
│       └── local_queue.py
│
├── config.py
└── main.py