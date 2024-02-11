'''Image process functions for ComfyUI nodes
by chflame https://github.com/chflame163
'''
import copy
import os
import re
import glob
import numpy as np
import torch
import scipy.ndimage
import cv2
import random
from typing import Union, List
from PIL import Image, ImageFilter, ImageChops, ImageDraw, ImageOps
from skimage import img_as_float, img_as_ubyte
import colorsys


def log(message):
    name = 'LayerStyle'
    print(f"# 😺dzNodes: {name} -> {message}")

'''Converter'''

def cv22ski(cv2_image:np.ndarray) -> np.array:
    return img_as_float(cv2_image)

def ski2cv2(ski:np.array) -> np.ndarray:
    return img_as_ubyte(ski)

def cv22pil(cv2_img:np.ndarray) -> Image:
    cv2_img = cv2.cvtColor(cv2_img, cv2.COLOR_BGR2RGB)
    return Image.fromarray(cv2_img)

def pil2cv2(pil_img:Image) -> np.array:
    np_img_array = np.asarray(pil_img)
    return cv2.cvtColor(np_img_array, cv2.COLOR_RGB2BGR)

def pil2tensor(image:Image) -> torch.Tensor:
    return torch.from_numpy(np.array(image).astype(np.float32) / 255.0).unsqueeze(0)

def np2tensor(img_np: Union[np.ndarray, List[np.ndarray]]) -> torch.Tensor:
    if isinstance(img_np, list):
        return torch.cat([np2tensor(img) for img in img_np], dim=0)
    return torch.from_numpy(img_np.astype(np.float32) / 255.0).unsqueeze(0)

def tensor2np(tensor: torch.Tensor) -> List[np.ndarray]:
    if len(tensor.shape) == 3:  # Single image
        return np.clip(255.0 * tensor.cpu().numpy(), 0, 255).astype(np.uint8)
    else:  # Batch of images
        return [np.clip(255.0 * t.cpu().numpy(), 0, 255).astype(np.uint8) for t in tensor]

def tensor2pil(t_image: torch.Tensor)  -> Image:
    return Image.fromarray(np.clip(255.0 * t_image.cpu().numpy().squeeze(), 0, 255).astype(np.uint8))

def image2mask(image:Image) -> torch.Tensor:
    _image = image.convert('RGBA')
    alpha = _image.split() [0]
    bg = Image.new("L", _image.size)
    _image = Image.merge('RGBA', (bg, bg, bg, alpha))
    ret_mask = torch.tensor([pil2tensor(_image)[0, :, :, 3].tolist()])
    return ret_mask

def mask2image(mask:torch.Tensor)  -> Image:
    masks = tensor2np(mask)
    for m in masks:
        _mask = Image.fromarray(m).convert("L")
        _image = Image.new("RGBA", _mask.size, color='white')
        _image = Image.composite(
            _image, Image.new("RGBA", _mask.size, color='black'), _mask)
    return _image

# def make_3d_mask(mask):
#     if len(mask.shape) == 4:
#         return mask.squeeze(0)
#     elif len(mask.shape) == 2:
#         return mask.unsqueeze(0)
#     return mask

'''Image Functions'''

# 颜色加深
def blend_color_burn(background_image:Image, layer_image:Image) -> Image:
    img_1 = cv22ski(pil2cv2(background_image))
    img_2 = cv22ski(pil2cv2(layer_image))
    img = 1 - (1 - img_2) / (img_1 + 0.001)
    mask_1 = img < 0
    mask_2 = img > 1
    img = img * (1 - mask_1)
    img = img * (1 - mask_2) + mask_2
    return cv22pil(ski2cv2(img))

# 颜色减淡
def blend_color_dodge(background_image:Image, layer_image:Image) -> Image:
    img_1 = cv22ski(pil2cv2(background_image))
    img_2 = cv22ski(pil2cv2(layer_image))
    img = img_2 / (1.0 - img_1 + 0.001)
    mask_2 = img > 1
    img = img * (1 - mask_2) + mask_2
    return cv22pil(ski2cv2(img))

# 线性加深
def blend_linear_burn(background_image:Image, layer_image:Image) -> Image:
    img_1 = cv22ski(pil2cv2(background_image))
    img_2 = cv22ski(pil2cv2(layer_image))
    img = img_1 + img_2 - 1
    mask_1 = img < 0
    img = img * (1 - mask_1)
    return cv22pil(ski2cv2(img))

# 线性减淡
def blend_linear_dodge(background_image:Image, layer_image:Image) -> Image:
    img_1 = cv22ski(pil2cv2(background_image))
    img_2 = cv22ski(pil2cv2(layer_image))
    img = img_1 + img_2
    mask_2 = img > 1
    img = img * (1 - mask_2) + mask_2
    return cv22pil(ski2cv2(img))

# 变亮
def blend_lighten(background_image:Image, layer_image:Image) -> Image:
    img_1 = cv22ski(pil2cv2(background_image))
    img_2 = cv22ski(pil2cv2(layer_image))
    img = img_1 - img_2
    mask = img > 0
    img = img_1 * mask + img_2 * (1 - mask)
    return cv22pil(ski2cv2(img))

# 变暗
def blend_dark(background_image:Image, layer_image:Image) -> Image:
    img_1 = cv22ski(pil2cv2(background_image))
    img_2 = cv22ski(pil2cv2(layer_image))
    img = img_1 - img_2
    mask = img < 0
    img = img_1 * mask + img_2 * (1 - mask)
    return cv22pil(ski2cv2(img))

# 滤色
def blend_screen(background_image:Image, layer_image:Image) -> Image:
    img_1 = cv22ski(pil2cv2(background_image))
    img_2 = cv22ski(pil2cv2(layer_image))
    img = 1 - (1 - img_1) * (1 - img_2)
    return cv22pil(ski2cv2(img))

# 叠加
def blend_overlay(background_image:Image, layer_image:Image) -> Image:
    img_1 = cv22ski(pil2cv2(background_image))
    img_2 = cv22ski(pil2cv2(layer_image))
    mask = img_2 < 0.5
    img = 2 * img_1 * img_2 * mask + (1 - mask) * (1 - 2 * (1 - img_1) * (1 - img_2))
    return cv22pil(ski2cv2(img))

# 柔光
def blend_soft_light(background_image:Image, layer_image:Image) -> Image:
    img_1 = cv22ski(pil2cv2(background_image))
    img_2 = cv22ski(pil2cv2(layer_image))
    mask = img_1 < 0.5
    T1 = (2 * img_1 - 1) * (img_2 - img_2 * img_2) + img_2
    T2 = (2 * img_1 - 1) * (np.sqrt(img_2) - img_2) + img_2
    img = T1 * mask + T2 * (1 - mask)
    return cv22pil(ski2cv2(img))

# 强光
def blend_hard_light(background_image:Image, layer_image:Image) -> Image:
    img_1 = cv22ski(pil2cv2(background_image))
    img_2 = cv22ski(pil2cv2(layer_image))
    mask = img_1 < 0.5
    T1 = 2 * img_1 * img_2
    T2 = 1 - 2 * (1 - img_1) * (1 - img_2)
    img = T1 * mask + T2 * (1 - mask)
    return cv22pil(ski2cv2(img))

# 亮光
def blend_vivid_light(background_image:Image, layer_image:Image) -> Image:
    img_1 = cv22ski(pil2cv2(background_image))
    img_2 = cv22ski(pil2cv2(layer_image))
    mask = img_1 < 0.5
    T1 = 1 - (1 - img_2) / (2 * img_1 + 0.001)
    T2 = img_2 / (2 * (1 - img_1) + 0.001)
    mask_1 = T1 < 0
    mask_2 = T2 > 1
    T1 = T1 * (1 - mask_1)
    T2 = T2 * (1 - mask_2) + mask_2
    img = T1 * mask + T2 * (1 - mask)
    return cv22pil(ski2cv2(img))

# 点光
def blend_pin_light(background_image:Image, layer_image:Image) -> Image:
    img_1 = cv22ski(pil2cv2(background_image))
    img_2 = cv22ski(pil2cv2(layer_image))
    mask_1 = img_2 < (img_1 * 2 - 1)
    mask_2 = img_2 > 2 * img_1
    T1 = 2 * img_1 - 1
    T2 = img_2
    T3 = 2 * img_1
    img = T1 * mask_1 + T2 * (1 - mask_1) * (1 - mask_2) + T3 * mask_2
    return cv22pil(ski2cv2(img))

# 线性光
def blend_linear_light(background_image:Image, layer_image:Image) -> Image:
    img_1 = cv22ski(pil2cv2(background_image))
    img_2 = cv22ski(pil2cv2(layer_image))
    img = img_2 + img_1 * 2 - 1
    mask_1 = img < 0
    mask_2 = img > 1
    img = img * (1 - mask_1)
    img = img * (1 - mask_2) + mask_2
    return cv22pil(ski2cv2(img))

def blend_hard_mix(background_image:Image, layer_image:Image) -> Image:
    img_1 = cv22ski(pil2cv2(background_image))
    img_2 = cv22ski(pil2cv2(layer_image))
    img = img_1 + img_2
    mask = img_1 + img_2 > 1
    img = img * (1 - mask) + mask
    img = img * mask
    return cv22pil(ski2cv2(img))

def shift_image(image:Image, distance_x:int, distance_y:int, background_color:str='#000000', cyclic:bool=False) -> Image:
    width = image.width
    height = image.height
    ret_image = Image.new('RGB', size=(width, height), color=background_color)
    for x in range(width):
        for y in range(height):
            if cyclic:
                    orig_x = x + distance_x
                    if orig_x > width-1 or orig_x < 0:
                        orig_x = abs(orig_x % width)
                    orig_y = y + distance_y
                    if orig_y > height-1 or orig_y < 0:
                        orig_y = abs(orig_y % height)

                    pixel = image.getpixel((orig_x, orig_y))
                    ret_image.putpixel((x, y), pixel)
            else:
                if x > -distance_x and y > -distance_y:  # 防止回转
                    if x + distance_x < width and y + distance_y < height:  # 防止越界
                        pixel = image.getpixel((x + distance_x, y + distance_y))
                        ret_image.putpixel((x, y), pixel)
    return ret_image

def chop_image(background_image:Image, layer_image:Image, blend_mode:str, opacity:int) -> Image:
    ret_image = background_image
    if blend_mode == 'normal':
        ret_image = copy.deepcopy(layer_image)
    if blend_mode == 'multply':
        ret_image = ImageChops.multiply(background_image,layer_image)
    if blend_mode == 'screen':
        ret_image = ImageChops.screen(background_image, layer_image)
    if blend_mode == 'add':
        ret_image = ImageChops.add(background_image, layer_image, 1, 0)
    if blend_mode == 'subtract':
        ret_image = ImageChops.subtract(background_image, layer_image, 1, 0)
    if blend_mode == 'difference':
        ret_image = ImageChops.difference(background_image, layer_image)
    if blend_mode == 'darker':
        ret_image = ImageChops.darker(background_image, layer_image)
    if blend_mode == 'lighter':
        ret_image = ImageChops.lighter(background_image, layer_image)
    if blend_mode == 'color_burn':
        ret_image = blend_color_burn(background_image, layer_image)
    if blend_mode == 'color_dodge':
        ret_image = blend_color_dodge(background_image, layer_image)
    if blend_mode == 'linear_burn':
        ret_image = blend_linear_burn(background_image, layer_image)
    if blend_mode == 'linear_dodge':
        ret_image = blend_linear_dodge(background_image, layer_image)
    if blend_mode == 'overlay':
        ret_image = blend_overlay(background_image, layer_image)
    if blend_mode == 'soft_light':
        ret_image = blend_soft_light(background_image, layer_image)
    if blend_mode == 'hard_light':
        ret_image = blend_hard_light(background_image, layer_image)
    if blend_mode == 'vivid_light':
        ret_image = blend_vivid_light(background_image, layer_image)
    if blend_mode == 'pin_light':
        ret_image = blend_pin_light(background_image, layer_image)
    if blend_mode == 'linear_light':
        ret_image = blend_linear_light(background_image, layer_image)
    if blend_mode == 'hard_mix':
        ret_image = blend_hard_mix(background_image, layer_image)
    # opacity
    if opacity == 0:
        ret_image = background_image
    elif opacity < 100:
        alpha = 1.0 - float(opacity) / 100
        ret_image = Image.blend(ret_image, background_image, alpha)
    return ret_image

def remove_background(image:Image, mask:Image, color:str) -> Image:
    width = image.width
    height = image.height
    ret_image = Image.new('RGB', size=(width, height), color=color)
    ret_image.paste(image, mask=mask)
    return ret_image

def gaussian_blur(image:Image, radius:int) -> Image:
    image = image.convert("RGBA")
    ret_image = image.filter(ImageFilter.GaussianBlur(radius=radius))
    return ret_image

def motion_blur(image:Image, angle:int, blur:int) -> Image:
    angle += 45
    blur *= 5
    image = np.array(pil2cv2(image))
    M = cv2.getRotationMatrix2D((blur / 2, blur / 2), angle, 1)
    motion_blur_kernel = np.diag(np.ones(blur))
    motion_blur_kernel = cv2.warpAffine(motion_blur_kernel, M, (blur, blur))
    motion_blur_kernel = motion_blur_kernel / blur
    blurred = cv2.filter2D(image, -1, motion_blur_kernel)
    # convert to uint8
    cv2.normalize(blurred, blurred, 0, 255, cv2.NORM_MINMAX)
    blurred = np.array(blurred, dtype=np.uint8)
    ret_image = cv22pil(blurred)
    return ret_image

def fit_resize_image(image:Image, target_width:int, target_height:int, fit:str, resize_sampler:str) -> Image:
    image = image.convert('RGB')
    orig_width, orig_height = image.size
    if image is not None:
        if fit == 'letterbox':
            if orig_width / orig_height > target_width / target_height:  # 更宽，上下留黑
                fit_width = target_width
                fit_height = int(target_width / orig_width * orig_height)
            else:  # 更瘦，左右留黑
                fit_height = target_height
                fit_width = int(target_height / orig_height * orig_width)
            fit_image = image.resize((fit_width, fit_height), resize_sampler)
            ret_image = Image.new('RGB', size=(target_width, target_height), color='black')
            ret_image.paste(fit_image, box=((target_width - fit_width)//2, (target_height - fit_height)//2))
        elif fit == 'crop':
            if orig_width / orig_height > target_width / target_height:  # 更宽，裁左右
                fit_width = int(orig_height * target_width / target_height)
                fit_image = image.crop(
                    ((orig_width - fit_width)//2, 0, (orig_width - fit_width)//2 + fit_width, orig_height))
            else:   # 更瘦，裁上下
                fit_height = int(orig_width * target_height / target_width)
                fit_image = image.crop(
                    (0, (orig_height-fit_height)//2, orig_width, (orig_height-fit_height)//2 + fit_height))
            ret_image = fit_image.resize((target_width, target_height), resize_sampler)
        else:
            ret_image = image.resize((target_width, target_height), resize_sampler)
    return  ret_image

def __rotate_expand(image:Image, angle:float, SSAA:int=0, method:str="lanczos") -> Image:
    images = pil2tensor(image)
    expand = "true"
    height, width = images[0, :, :, 0].shape

    def rotate_tensor(tensor):
        resize_sampler = Image.LANCZOS
        rotate_sampler = Image.BICUBIC
        if method == "bicubic":
            resize_sampler = Image.BICUBIC
            rotate_sampler = Image.BICUBIC
        elif method == "hamming":
            resize_sampler = Image.HAMMING
            rotate_sampler = Image.BILINEAR
        elif method == "bilinear":
            resize_sampler = Image.BILINEAR
            rotate_sampler = Image.BILINEAR
        elif method == "box":
            resize_sampler = Image.BOX
            rotate_sampler = Image.NEAREST
        elif method == "nearest":
            resize_sampler = Image.NEAREST
            rotate_sampler = Image.NEAREST
        img = tensor2pil(tensor)
        if SSAA > 1:
            img_us_scaled = img.resize((width * SSAA, height * SSAA), resize_sampler)
            img_rotated = img_us_scaled.rotate(angle, rotate_sampler, expand == "true", fillcolor=(0, 0, 0, 0))
            img_down_scaled = img_rotated.resize((img_rotated.width // SSAA, img_rotated.height // SSAA), resize_sampler)
            result = pil2tensor(img_down_scaled)
        else:
            img_rotated = img.rotate(angle, rotate_sampler, expand == "true", fillcolor=(0, 0, 0, 0))
            result = pil2tensor(img_rotated)
        return result

    if angle == 0.0 or angle == 360.0:
        return tensor2pil(images)
    else:
        rotated_tensor = torch.stack([rotate_tensor(images[i]) for i in range(len(images))])
        return tensor2pil(rotated_tensor).convert('RGB')

def image_rotate_extend_with_alpha(image:Image, angle:float, alpha:Image=None, method:str="lanczos", SSAA:int=0) -> tuple:
    _image = __rotate_expand(image.convert('RGB'), angle, SSAA, method)
    if angle is not None:
        _alpha = __rotate_expand(alpha.convert('RGB'), angle, SSAA, method)
        ret_image = RGB2RGBA(_image, _alpha)
    else:
        ret_image = _image
    return (_image, _alpha, ret_image)


def create_gradient(start_color_inhex:str, end_color_inhex:str, width:int, height:int) -> Image:
    start_color = Hex_to_RGB(start_color_inhex)
    end_color = Hex_to_RGB(end_color_inhex)
    ret_image = Image.new("RGB", (width, height), start_color)
    draw = ImageDraw.Draw(ret_image)
    for i in range(height):
        R = int(start_color[0] * (height - i) / height + end_color[0] * i / height)
        G = int(start_color[1] * (height - i) / height + end_color[1] * i / height)
        B = int(start_color[2] * (height - i) / height + end_color[2] * i / height)
        color = (R, G, B)
        draw.line((0, i, width, i), fill=color)
    return ret_image

def gradient(start_color_inhex:str, end_color_inhex:str, width:int, height:int, angle:float, ) -> Image:
    radius = int((width + height) / 4)
    g = create_gradient(start_color_inhex, end_color_inhex, radius, radius)
    _canvas = Image.new('RGB', size=(radius, radius*3), color=start_color_inhex)
    top = Image.new('RGB', size=(radius, radius), color=start_color_inhex)
    bottom = Image.new('RGB', size=(radius, radius),color=end_color_inhex)
    _canvas.paste(top, box=(0, 0, radius, radius))
    _canvas.paste(g, box=(0, radius, radius, radius * 2))
    _canvas.paste(bottom,box=(0, radius * 2, radius, radius * 3))
    _canvas = _canvas.resize((radius * 3, radius * 3))
    _canvas = __rotate_expand(_canvas,angle)
    center = int(_canvas.width / 2)
    _x = int(width / 3)
    _y = int(height / 3)
    ret_image = _canvas.crop((center - _x, center - _y, center + _x, center + _y))
    ret_image = ret_image.resize((width, height))
    return ret_image

def draw_rect(image:Image, x:int, y:int, width:int, height:int, line_color:str, line_width:int,
              box_color:str=None) -> Image:
    image = image.convert('RGBA')
    draw = ImageDraw.Draw(image)
    draw.rectangle((x, y, x + width, y + height), fill=box_color, outline=line_color, width=line_width, )
    return image

def draw_border(image:Image, border_width:int, color:str='#FFFFFF') -> Image:
    return ImageOps.expand(image, border=border_width, fill=color)

def get_image_color_tone(image:Image) -> str:
    image = image.convert('RGB')
    max_score = 0.0001
    dominant_color = None
    for count, (r, g, b) in image.getcolors(image.size[0] * image.size[1]):
        saturation = colorsys.rgb_to_hsv(r / 255.0, g / 255.0, b / 255.0)[1]
        y = min(abs(r * 2104 + g * 4130 + b * 802 + 4096 + 131072) >> 13,235)
        y = (y - 16.0) / (235 - 16)
        if y>0.9:
            continue
        score = (saturation+0.1)*count
        if score > max_score:
            max_score = score
            dominant_color = (r, g, b)
        ret_color = RGB_to_Hex(dominant_color)
    return ret_color

def get_image_color_average(image:Image) -> str:
    image = image.convert('RGB')
    width, height = image.size
    total_red = 0
    total_green = 0
    total_blue = 0
    for y in range(height):
        for x in range(width):
            rgb = image.getpixel((x, y))
            total_red += rgb[0]
            total_green += rgb[1]
            total_blue += rgb[2]

    average_red = total_red // (width * height)
    average_green = total_green // (width * height)
    average_blue = total_blue // (width * height)
    color = (average_red, average_green, average_blue)
    ret_color = RGB_to_Hex(color)
    return ret_color

def get_image_bright_average(image:Image) -> int:
    image = image.convert('L')
    width, height = image.size
    total_bright = 0
    pixels = 0
    for y in range(height):
        for x in range(width):
            b = image.getpixel((x, y))
            if b > 1:  # 排除死黑
                pixels += 1
                total_bright += b
    return int(total_bright / pixels)

def image_channel_split(image:Image, mode = 'RGBA') -> tuple:
    _image = image.convert('RGBA')
    channel1 = Image.new('L', size=_image.size, color='black')
    channel2 = Image.new('L', size=_image.size, color='black')
    channel3 = Image.new('L', size=_image.size, color='black')
    channel4 = Image.new('L', size=_image.size, color='black')
    if mode == 'RGBA':
        channel1, channel2, channel3, channel4 = _image.split()
    if mode == 'RGB':
        channel1, channel2, channel3 = _image.convert('RGB').split()
    if mode == 'YCbCr':
        channel1, channel2, channel3 = _image.convert('YCbCr').split()
    if mode == 'LAB':
        channel1, channel2, channel3 = _image.convert('LAB').split()
    if mode == 'HSV':
        channel1, channel2, channel3 = _image.convert('HSV').split()
    return channel1, channel2, channel3, channel4

def image_channel_merge(channels:tuple, mode = 'RGB' ) -> Image:
    channel1 = channels[0].convert('L')
    channel2 = channels[1].convert('L')
    channel3 = channels[2].convert('L')
    channel4 = Image.new('L', size=channel1.size, color='white')
    if mode == 'RGBA':
        if len(channels) > 3:
            channel4 = channels[3].convert('L')
        ret_image = Image.merge('RGBA',[channel1, channel2, channel3, channel4])
    elif mode == 'RGB':
        ret_image = Image.merge('RGB', [channel1, channel2, channel3])
    elif mode == 'YCbCr':
        ret_image = Image.merge('YCbCr', [channel1, channel2, channel3]).convert('RGB')
    elif mode == 'LAB':
        ret_image = Image.merge('LAB', [channel1, channel2, channel3]).convert('RGB')
    elif mode == 'HSV':
        ret_image = Image.merge('HSV', [channel1, channel2, channel3]).convert('RGB')
    return ret_image

def image_gray_offset(image:Image, offset:int) -> Image:
    image = image.convert('L')
    width = image.width
    height = image.height
    ret_image = Image.new('L', size=(width, height), color='black')
    for x in range(width):
        for y in range(height):
                pixel = image.getpixel((x, y))
                _pixel = pixel + offset
                if _pixel > 255:
                    _pixel = 255
                if _pixel < 0:
                    _pixel = 0
                ret_image.putpixel((x, y), _pixel)
    return ret_image

def image_hue_offset(image:Image, offset:int) -> Image:
    image = image.convert('L')
    width = image.width
    height = image.height
    ret_image = Image.new('L', size=(width, height), color='black')
    for x in range(width):
        for y in range(height):
                pixel = image.getpixel((x, y))
                _pixel = pixel + offset
                if _pixel > 255:
                    _pixel -= 256
                if _pixel < 0:
                    _pixel += 256
                ret_image.putpixel((x, y), _pixel)
    return ret_image

def gamma_trans(image:Image, gamma:float) -> Image:
    cv2_image = pil2cv2(image)
    gamma_table = [np.power(x/255.0,gamma)*255.0 for x in range(256)]
    gamma_table = np.round(np.array(gamma_table)).astype(np.uint8)
    _corrected = cv2.LUT(cv2_image,gamma_table)
    return cv22pil(_corrected)

def lut_apply(image:Image, lut_file:str) -> Image:
    _image = image.convert('RGB')
    width = _image.width
    height = _image.height
    lut_cube = []
    with open(lut_file, 'r') as f:
        lut = f.readlines()
        for line in lut:
            if not has_letters(line):
                li = line.strip('\n').split(' ')
                # B
                li[0] = float(li[0]) * 255
                # G
                li[1] = float(li[1]) * 255
                # R
                li[2] = float(li[2]) * 255
                lut_cube.append(li)
    for x in range(width):
        for y in range(height):
            pixel = _image.getpixel((x, y))
            R_pos = round(pixel[0] / 255 * 32)
            G_pos = round(pixel[1] / 255 * 32)
            B_pos = round(pixel[2] / 255 * 32)
            index = R_pos + G_pos * 33 + B_pos * 33 * 33
            new_pixel = (round(lut_cube[index][0]), round(lut_cube[index][1]), round(lut_cube[index][2]))
            _image.putpixel((x, y), new_pixel)
    return _image

def color_adapter(image:Image, ref_image:Image) -> Image:
    image = pil2cv2(image)
    ref_image = pil2cv2(ref_image)
    image = cv2.cvtColor(image, cv2.COLOR_BGR2LAB)
    image_mean, image_std = calculate_mean_std(image)
    ref_image = cv2.cvtColor(ref_image, cv2.COLOR_BGR2LAB)
    ref_image_mean, ref_image_std = calculate_mean_std(ref_image)
    _image = ((image - image_mean) * (ref_image_std / image_std)) + ref_image_mean
    np.putmask(_image, _image > 255, values=255)
    np.putmask(_image, _image < 0, values=0)
    ret_image = cv2.cvtColor(cv2.convertScaleAbs(_image), cv2.COLOR_LAB2BGR)
    return cv22pil(ret_image)

def calculate_mean_std(image:Image):
    mean, std = cv2.meanStdDev(image)
    mean = np.hstack(np.around(mean, decimals=2))
    std = np.hstack(np.around(std, decimals=2))
    return mean, std

def image_watercolor(image:Image, level:int=50) -> Image:
    img = pil2cv2(image)
    img = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)
    factor = (level / 128.0) ** 2
    sigmaS= int((image.width + image.height) / 5.0 * factor) + 1
    sigmaR = sigmaS / 32.0 * factor + 0.002
    img_color = cv2.stylization(img, sigma_s=sigmaS, sigma_r=sigmaR)
    ret_image = cv2.cvtColor(img_color, cv2.COLOR_BGR2RGB)
    return cv22pil(ret_image)


def image_beauty(image:Image, level:int=50) -> Image:
    img = pil2cv2(image)
    img = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)
    factor = (level / 50.0)**2
    d = int((image.width + image.height) / 256 * factor)
    sigmaColor = int((image.width + image.height) / 256 * factor)
    sigmaSpace = int((image.width + image.height) / 160 * factor)
    img_bit = cv2.bilateralFilter(src=img, d=d, sigmaColor=sigmaColor, sigmaSpace=sigmaSpace)
    ret_image = cv2.cvtColor(img_bit, cv2.COLOR_BGR2RGB)
    return cv22pil(ret_image)


'''Mask Functions'''

def expand_mask(mask:torch.Tensor, grow:int, blur:int) -> torch.Tensor:
    # grow
    c = 0
    kernel = np.array([[c, 1, c],
                       [1, 1, 1],
                       [c, 1, c]])
    growmask = mask.reshape((-1, mask.shape[-2], mask.shape[-1]))
    out = []
    for m in growmask:
        output = m.numpy()
        for _ in range(abs(grow)):
            if grow < 0:
                output = scipy.ndimage.grey_erosion(output, footprint=kernel)
            else:
                output = scipy.ndimage.grey_dilation(output, footprint=kernel)
        output = torch.from_numpy(output)
        out.append(output)
    # blur
    for idx, tensor in enumerate(out):
        pil_image = tensor2pil(tensor.cpu().detach())
        pil_image = pil_image.filter(ImageFilter.GaussianBlur(blur))
        out[idx] = pil2tensor(pil_image)
    ret_mask = torch.cat(out, dim=0)
    return ret_mask

def mask_invert(mask:torch.Tensor) -> torch.Tensor:
    return 1 - mask

def subtract_mask(masks_a:torch.Tensor, masks_b:torch.Tensor) -> torch.Tensor:
    return torch.clamp(masks_a - masks_b, 0, 255)

def RGB2RGBA(image:Image, mask:Image) -> Image:
    (R, G, B) = image.convert('RGB').split()
    return Image.merge('RGBA', (R, G, B, mask.convert('L')))

def min_bounding_rect(image:Image) -> tuple:
    cv2_image = pil2cv2(image)
    gray = cv2.cvtColor(cv2_image, cv2.COLOR_BGR2GRAY)
    ret, thresh = cv2.threshold(gray, 127, 255, 0)
    contours, _ = cv2.findContours(thresh, 1, 2)
    x, y, width, height = 0, 0, 0, 0
    area = 0
    for contour in contours:
        _x, _y, _w, _h = cv2.boundingRect(contour)
        _area = _w * _h
        if _area > area:
            area = _area
            x, y, width, height = _x, _y, _w, _h

    return (x, y, width, height)

def max_inscribed_rect(image:Image) -> tuple:
    img = pil2cv2(image)
    img_gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    ret, img_bin = cv2.threshold(img_gray, 127, 255, cv2.THRESH_BINARY)
    contours, _ = cv2.findContours(img_bin, cv2.RETR_CCOMP, cv2.CHAIN_APPROX_SIMPLE)
    contour = contours[0].reshape(len(contours[0]), 2)
    rect = []
    for i in range(len(contour)):
        x1, y1 = contour[i]
        for j in range(len(contour)):
            x2, y2 = contour[j]
            area = abs(y2 - y1) * abs(x2 - x1)
            rect.append(((x1, y1), (x2, y2), area))
    all_rect = sorted(rect, key=lambda x: x[2], reverse=True)
    if all_rect:
        best_rect_found = False
        index_rect = 0
        nb_rect = len(all_rect)
        while not best_rect_found and index_rect < nb_rect:
            rect = all_rect[index_rect]
            (x1, y1) = rect[0]
            (x2, y2) = rect[1]
            valid_rect = True
            x = min(x1, x2)
            while x < max(x1, x2) + 1 and valid_rect:
                if any(img[y1, x]) == 0 or any(img[y2, x]) == 0:
                    valid_rect = False
                x += 1
            y = min(y1, y2)
            while y < max(y1, y2) + 1 and valid_rect:
                if any(img[y, x1]) == 0 or any(img[y, x2]) == 0:
                    valid_rect = False
                y += 1
            if valid_rect:
                best_rect_found = True
            index_rect += 1
    #较小的数值排前面
    log(f"x1={x1}, y1={y1},x2={x2}, y2={y2}")
    x1, y1, x2, y2 = min(x1, x2), min(y1, y2), max(x1, x2), max(y1, y2)
    return (x1, y1, x2 - x1, y2 - y1)

def gray_threshold(image:Image, thresh:int=127, otsu:bool=False) -> Image:
    cv2_image = pil2cv2(image)
    gray = cv2.cvtColor(cv2_image, cv2.COLOR_BGR2GRAY)
    if otsu:
        _, thresh =  cv2.threshold(gray,0,255,cv2.THRESH_BINARY+cv2.THRESH_OTSU)
    else:
        _, thresh = cv2.threshold(gray, thresh, 255, cv2.THRESH_TOZERO)

    return cv22pil(thresh).convert('L')

def image_to_colormap(image:Image, index:int) -> Image:
    return cv22pil(cv2.applyColorMap(pil2cv2(image), index))

'''Color Functions'''

def RGB_to_Hex(RGB) -> str:
    color = '#'
    for i in RGB:
        num = int(i)
        color += str(hex(num))[-2:].replace('x', '0').upper()
    return color

def Hex_to_RGB(inhex) -> tuple:
    rval = inhex[1:3]
    gval = inhex[3:5]
    bval = inhex[5:]
    rgb = (int(rval, 16), int(gval, 16), int(bval, 16))
    return tuple(rgb)

def RGB_to_HSV(RGB:tuple) -> list:
    HSV = colorsys.rgb_to_hsv(RGB[0] / 255.0, RGB[1] / 255.0, RGB[2] / 255.0)
    return [int(x * 360) for x in HSV]

'''Value Functions'''

def step_value(start_value, end_value, total_step, step) -> float:  # 按当前步数在总步数中的位置返回比例值
    factor = step / total_step
    return (end_value - start_value) * factor + start_value

def step_color(start_color_inhex:str, end_color_inhex:str, total_step:int, step:int) -> str:  # 按当前步数在总步数中的位置返回比例颜色
    start_color = tuple(Hex_to_RGB(start_color_inhex))
    end_color = tuple(Hex_to_RGB(end_color_inhex))
    start_R, start_G, start_B = start_color[0], start_color[1], start_color[2]
    end_R, end_G, end_B = end_color[0], end_color[1], end_color[2]
    ret_color = (int(step_value(start_R, end_R, total_step, step)),
                 int(step_value(start_G, end_G, total_step, step)),
                 int(step_value(start_B, end_B, total_step, step)),
                 )
    return RGB_to_Hex(ret_color)

def has_letters(string:str) -> bool:
    pattern = r'[a-zA-Z]'
    match = re.search(pattern, string)
    if match:
        return True
    else:
        return False

def random_numbers(total:int, random_range:int, seed:int=0, sum_of_numbers:int=0) -> list:
    random.seed(seed)
    numbers = [random.randint(-random_range//2, random_range//2) for _ in range(total - 1)]
    avg = sum(numbers) // total
    ret_list = []
    for i in numbers:
        ret_list.append(i - avg)
    ret_list.append(sum_of_numbers - sum(ret_list))
    return ret_list

'''CLASS'''

class AnyType(str):
  """A special class that is always equal in not equal comparisons. Credit to pythongosssss"""
  def __ne__(self, __value: object) -> bool:
    return False

'''Constant'''

chop_mode = ['normal', 'multply', 'screen', 'add', 'subtract', 'difference', 'darker', 'lighter',
             'color_burn', 'color_dodge', 'linear_burn', 'linear_dodge', 'overlay',
             'soft_light', 'hard_light', 'vivid_light', 'pin_light', 'linear_light', 'hard_mix']

'''Load INI File'''

default_lut_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.normpath(__file__))), 'lut')
default_font_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.normpath(__file__))), 'font')
resource_dir_ini_file = os.path.join(os.path.dirname(os.path.dirname(os.path.normpath(__file__))), "resource_dir.ini")

try:
    with open(resource_dir_ini_file, 'r') as f:
        ini = f.readlines()
        for line in ini:
            if line.startswith('LUT_dir='):
                _ldir = line[line.find('=') + 1:].rstrip().lstrip()
                if os.path.exists(_ldir):
                    default_lut_dir = _ldir
                else:
                    log(f'ERROR: invalid LUT directory, default to be used. check {resource_dir_ini_file}')
            elif line.startswith('FONT_dir='):
                _fdir = line[line.find('=') + 1:].rstrip().lstrip()
                if os.path.exists(_fdir):
                    default_font_dir = _fdir
                else:
                    log(f'ERROR: invalid FONT directory, default to be used. check {resource_dir_ini_file}')
except Exception as e:
    log(f'ERROR: {resource_dir_ini_file} ' + repr(e))

__lut_file_list = glob.glob(default_lut_dir + '/*.cube')
LUT_DICT = {}
for i in range(len(__lut_file_list)):
    _, __filename =  os.path.split(__lut_file_list[i])
    LUT_DICT[__filename] = __lut_file_list[i]
LUT_LIST = list(LUT_DICT.keys())
log(f'find {len(LUT_LIST)} LUTs in {default_lut_dir}')

__font_file_list = glob.glob(default_font_dir + '/*.ttf')
__font_file_list.extend(glob.glob(default_font_dir + '/*.otf'))
FONT_DICT = {}
for i in range(len(__font_file_list)):
    _, __filename =  os.path.split(__font_file_list[i])
    FONT_DICT[__filename] = __font_file_list[i]
FONT_LIST = list(FONT_DICT.keys())
log(f'find {len(FONT_LIST)} Fonts in {default_font_dir}')
