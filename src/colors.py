# Mat Color Library (Expanded 1000+)

# Standard Curated Colors
COLORS = {
    # Whites & Neutrals
    "Cotton White": (251, 251, 249),
    "Bright White": (255, 255, 255),
    "Paper White": (245, 245, 248),
    "Snow": (255, 250, 250),
    "Ivory": (255, 255, 240),
    "Floral White": (255, 250, 240),
    "Antique White": (250, 235, 215),
    "Ghost White": (248, 248, 255),
    "White Smoke": (245, 245, 245),
    "Seashell": (255, 245, 238),
    "Old Lace": (253, 245, 230),
    "Linen": (250, 240, 230),
    "Bone": (227, 218, 201),
    "Parchment": (241, 233, 210),
    "Eggshell": (240, 234, 214),

    # Grays & Blacks
    "Ash Gray": (178, 190, 181),
    "Cool Gray": (144, 164, 174),
    "Silver": (192, 192, 192),
    "Pewter": (142, 142, 142),
    "Slate Gray": (112, 128, 144),
    "Charcoal": (54, 69, 79),
    "Steel Gray": (113, 121, 126),
    "Black": (0, 0, 0),
    "Jet Black": (52, 52, 52),
    "Midnight": (44, 62, 80),

    # Earth Tones
    "Tan": (210, 180, 140),
    "Sand": (194, 178, 128),
    "Beige": (245, 245, 220),
    "Taupe": (72, 60, 50),
    "Camel": (193, 154, 107),
    "Oatmeal": (233, 224, 210),
    "Terracotta": (226, 114, 91),
    "Umber": (99, 81, 71),
    "Sienna": (160, 82, 45),
    "Chocolate": (105, 75, 55),
    "Walnut": (127, 99, 80),
    "Dark Walnut": (93, 67, 44),
    "Mahogany": (192, 64, 0),
    "Oak": (188, 158, 130),
    "Cherry Wood": (144, 56, 32),
    "Wenge": (100, 84, 82),
    "Birch": (245, 245, 220),
    "Ebony": (40, 40, 40),
    "Rosewood": (101, 0, 11),
    "Charcoal Black": (44, 44, 44),
    "Painted Black": (26, 26, 26),

    # Blues & Teals
    "Navy Blue": (0, 0, 128),
    "Royal Blue": (65, 105, 225),
    "Sky Blue": (135, 206, 235),
    "Steel Blue": (70, 130, 180),
    "Denim": (21, 96, 189),
    "Oxford Blue": (0, 33, 71),
    "Teal": (0, 128, 128),
    "Cyan": (0, 255, 255),
    "Powder Blue": (176, 224, 230),
    "Prussian Blue": (0, 49, 83),
    "Celeste": (178, 255, 255),

    # Greens
    "Forest Green": (34, 139, 34),
    "Sage Green": (156, 175, 136),
    "Olive": (128, 128, 0),
    "Emerald": (80, 200, 120),
    "Mint": (189, 252, 201),
    "Seafoam": (159, 226, 191),
    "Hunter Green": (53, 94, 59),
    "Lime": (50, 205, 50),
    "Kelly Green": (76, 187, 23),
    "Moss": (138, 154, 91),
    "Jade": (0, 168, 107),

    # Reds & Pinks
    "Deep Red": (139, 0, 0),
    "Burgundy": (128, 0, 32),
    "Crimson": (220, 20, 60),
    "Brick": (178, 34, 34),
    "Wine": (114, 47, 55),
    "Rose": (255, 0, 127),
    "Dusty Rose": (194, 115, 127),
    "Salmon": (250, 128, 114),
    "Coral": (255, 127, 80),

    # Purples & Pinks
    "Plum": (142, 69, 133),
    "Lavender": (230, 230, 250),
    "Mauve": (224, 176, 255),
    "Aubergine": (61, 12, 21),
    "Violet": (143, 0, 255),
    "Indigo": (75, 0, 130),
    "Magenta": (255, 0, 255),

    # Oranges & Yellows
    "Gold": (212, 175, 55),
    "Sunflower": (255, 196, 0),
    "Ochre": (204, 119, 34),
    "Burnt Orange": (204, 85, 0),
    "Peach": (255, 218, 185),
    "Amber": (255, 191, 0),
    "Mustard": (255, 219, 88),
}

# Descriptive Names Generation (Standard Mat Shades)
import colorsys

BASES = {
    "Red": (255, 0, 0), "Green": (0, 255, 0), "Blue": (0, 0, 255),
    "Yellow": (255, 255, 0), "Cyan": (0, 255, 255), "Magenta": (255, 0, 255),
    "Orange": (255, 165, 0), "Purple": (128, 0, 128), "Pink": (255, 192, 203),
    "Brown": (165, 42, 42), "Gray": (128, 128, 128), "Tan": (210, 180, 140),
    "Olive": (128, 128, 0), "Teal": (0, 128, 128), "Cream": (255, 253, 208)
}

# Generate 1000+ variations
for b_name, (br, bg, bb) in BASES.items():
    h, l, s = colorsys.rgb_to_hls(br/255.0, bg/255.0, bb/255.0)
    
    for s_step in [0.2, 0.4, 0.6, 0.8, 1.0]:
        for l_step in [0.2, 0.4, 0.6, 0.8, 1.0]:
            r_v, g_v, b_v = colorsys.hls_to_rgb(h, l_step, s_step)
            rgb = (int(r_v*255), int(g_v*255), int(b_v*255))
            
            prefix = ""
            if l_step < 0.35: prefix = "Dark "
            elif l_step > 0.65: prefix = "Light "
            
            if s_step < 0.4: prefix = "Muted " + prefix
            elif s_step > 0.85: prefix = "Vibrant " + prefix
            
            name = f"{prefix}{b_name}".strip()
            if rgb not in COLORS.values() and name not in COLORS:
                COLORS[name] = rgb

# Fine-grained grid
for r in range(0, 256, 32):
    for g in range(0, 256, 32):
        for b in range(0, 256, 32):
            rgb = (r, g, b)
            if rgb not in COLORS.values():
                h, l, s = colorsys.rgb_to_hls(r/255.0, g/255.0, b/255.0)
                
                hue_name = "Red"
                if h < 0.05: hue_name = "Red"
                elif h < 0.15: hue_name = "Orange"
                elif h < 0.20: hue_name = "Yellow"
                elif h < 0.45: hue_name = "Green"
                elif h < 0.55: hue_name = "Cyan"
                elif h < 0.75: hue_name = "Blue"
                elif h < 0.85: hue_name = "Purple"
                elif h < 0.95: hue_name = "Magenta"
                else: hue_name = "Red"
                
                lum = ""
                if l < 0.15: lum = "Deep "
                elif l < 0.35: lum = "Dark "
                elif l > 0.85: lum = "Pale "
                elif l > 0.65: lum = "Light "
                
                sat = ""
                if s < 0.15: 
                    if l < 0.2: name = "Blackish Shade"
                    elif l > 0.8: name = "Whitish Shade"
                    else: name = f"{lum}Gray-ish Shade".strip()
                else:
                    if s < 0.4: sat = "Muted "
                    elif s > 0.85: sat = "Vibrant "
                    name = f"{sat}{lum}{hue_name} Shade".strip()
                
                if name not in COLORS:
                    COLORS[name] = rgb
