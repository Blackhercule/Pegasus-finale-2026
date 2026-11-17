# Modèle de détection de visages

`face_detection_yunet_2023mar.onnx` : **YuNet**, un petit réseau de neurones (230 Ko) qui
détecte les visages. Il sert au masquage des photos (`application/anonymiser.py`), en plus des
cascades livrées avec OpenCV.

- Source : https://github.com/opencv/opencv_zoo/tree/main/models/face_detection_yunet
- Licence : MIT (Shiqi Yu), texte dans `LICENCE-YuNet.txt`
- Article : « YuNet: A tiny millisecond-level face detector », Machine Intelligence Research, 2023
- Empreinte SHA-256 :
  `8f2383e4dd3cfbb4553ea8718107fc0423210dc964f9f4280604804ed2552fa4`

Téléchargé une fois, pendant la préparation, et rangé ici : rien n'est téléchargé à l'exécution.
Il est lu par `cv2.FaceDetectorYN`, présent dans `opencv-python-headless` 4.10 : aucune
bibliothèque de plus.
