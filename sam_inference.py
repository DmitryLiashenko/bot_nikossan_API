import torch
import numpy as np
import cv2
from segment_anything import SamAutomaticMaskGenerator, sam_model_registry


def generate_mask(image_path):
    model_type = "vit_h"
    checkpoint = "sam_vit_h_4b8939.pth"

    # Загружаем state_dict с map_location="cpu"
    state_dict = torch.load(checkpoint, map_location=torch.device("cpu"))

    # Инициализируем модель SAM без автоматической загрузки чекпоинта
    sam = sam_model_registry[model_type](checkpoint=None)

    # Загружаем веса
    sam.load_state_dict(state_dict)
    sam.to("cpu")
    sam.eval()

    # Генерация маски
    mask_generator = SamAutomaticMaskGenerator(sam)
    image = cv2.imread(image_path)
    image = cv2.cvtColor(image, cv2.COLOR_BGR2RGB)

    masks = mask_generator.generate(image)

    # Сохраняем первую найденную маску
    if masks:
        mask = masks[0]["segmentation"].astype(np.uint8) * 255
        cv2.imwrite("mask.png", mask)
        return "mask.png"
    else:
        return None
