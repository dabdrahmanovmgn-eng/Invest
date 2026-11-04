import warnings
from pathlib import Path

from django.core.exceptions import ValidationError
from django.db.models.fields.files import FieldFile
from PIL import Image, UnidentifiedImageError

MAX_IMAGE_BYTES = 8 * 1024 * 1024

def validate_image(value):
    """Проверяем декодирование и фактический формат, а не только расширение."""
    close_after = isinstance(value, FieldFile) and value.closed
    try:
        if value.size > MAX_IMAGE_BYTES:
            raise ValidationError("Изображение должно быть не больше 8 МБ.")
        value.seek(0)
        with warnings.catch_warnings():
            warnings.simplefilter("error", Image.DecompressionBombWarning)
            with Image.open(value) as image:
                expected = {"PNG": {".png"}, "JPEG": {".jpg", ".jpeg"}, "WEBP": {".webp"}}
                if image.format not in expected or Path(value.name).suffix.lower() not in expected[image.format]:
                    raise ValidationError("Выберите PNG, JPEG или WebP с правильным расширением.")
                if max(image.size) > 12000 or image.width * image.height > 40_000_000:
                    raise ValidationError("Максимум 12000 px по стороне и 40 Мп.")
                image.verify()
            value.seek(0)
            with Image.open(value) as image:
                image.load()
    except (UnidentifiedImageError, OSError, ValueError, SyntaxError, EOFError, Image.DecompressionBombError, Image.DecompressionBombWarning):
        raise ValidationError("Изображение повреждено или имеет недопустимое разрешение.") from None
    finally:
        if close_after:
            value.close()
        else:
            value.seek(0)
