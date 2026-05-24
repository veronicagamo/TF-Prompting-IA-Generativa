# -*- coding: utf-8 -*-
import json

with open('ucm_food_database.json', 'r', encoding='utf-8') as f:
    db = {item['name'].lower(): item for item in json.load(f)}

foods = {
    "avena": db["avena"],
    "pechuga_pollo": db["pechuga de pollo"],
    "arroz_integral": db["arroz integral"],
    "huevo": db["huevo de gallina"],
    "clara": db["clara de huevo"],
    "aceite": db["aceite de oliva"],
    "pan_integral": db["pan integral"],
    "platano": db["plátano"],
    "ternera_magra": db["ternera magra"],
    "pasta_integral": db["pasta integral"],
    "nuez": db["nuez sin cascara"],
    "patata_nueva": db["patata nueva"]
}
foods["whey"] = {"kcal": 360.0, "proteins": 80.0, "carbs": 3.0, "fats": 2.0, "fiber": 0.0}

def calc(diet):
    kcal = sum(foods[f]["kcal"] * g / 100.0 for f, g in diet.items())
    p = sum(foods[f]["proteins"] * g / 100.0 for f, g in diet.items())
    c = sum(foods[f]["carbs"] * g / 100.0 for f, g in diet.items())
    g = sum(foods[f]["fats"] * g / 100.0 for f, g in diet.items())
    fib = sum(foods[f]["fiber"] * g / 100.0 for f, g in diet.items())
    return kcal, p, c, g, fib

# Base recipes for 2148 kcal, 165g P, 203g C, 75g G
base_menus = {
    "Lunes": {"avena": 53, "clara": 351, "huevo": 100, "pechuga_pollo": 299, "arroz_integral": 199, "aceite": 33, "platano": 100, "whey": 30},
    "Martes": {"pan_integral": 109, "clara": 283, "huevo": 100, "ternera_magra": 375, "pasta_integral": 199, "aceite": 18, "platano": 120, "nuez": 15},
    "Miércoles": {"avena": 200, "clara": 379, "huevo": 100, "pechuga_pollo": 335, "patata_nueva": 367, "aceite": 22, "platano": 150, "whey": 0},
    "Jueves": {"pan_integral": 82, "clara": 394, "huevo": 100, "ternera_magra": 395, "arroz_integral": 188, "aceite": 21, "platano": 100, "nuez": 20},
    "Viernes": {"avena": 83, "clara": 330, "huevo": 100, "pechuga_pollo": 346, "pasta_integral": 189, "aceite": 25, "platano": 150, "whey": 0},
    "Sábado": {"pan_integral": 148, "clara": 371, "huevo": 100, "ternera_magra": 383, "patata_nueva": 492, "aceite": 30, "platano": 150, "nuez": 20},
    "Domingo": {"avena": 73, "clara": 395, "huevo": 100, "pechuga_pollo": 371, "arroz_integral": 181, "aceite": 28, "platano": 120, "whey": 0}
}

# Target for testing (e.g. 85kg user, target is 2500 kcal, 185g P, 240g C, 85g G)
target_kcal = 2500
target_p = 185
target_c = 240
target_g = 85

scale_p = target_p / 165.0
scale_c = target_c / 203.0
scale_g = target_g / 75.0

print(f"Scales: P={scale_p:.2f}, C={scale_c:.2f}, G={scale_g:.2f}")

for day, diet in base_menus.items():
    scaled_diet = {}
    for ing, g in diet.items():
        if ing in ["clara", "pechuga_pollo", "ternera_magra", "whey"]:
            scaled_diet[ing] = max(10, round(g * scale_p))
        elif ing in ["avena", "arroz_integral", "pan_integral", "pasta_integral", "patata_nueva"]:
            scaled_diet[ing] = max(10, round(g * scale_c))
        elif ing in ["aceite", "nuez"]:
            scaled_diet[ing] = max(5, round(g * scale_g))
        else:
            # egg, banana remain constant or scale minimally
            scaled_diet[ing] = g
            
    kcal, p, c, g, fib = calc(scaled_diet)
    print(f"=== {day} ===")
    print("Base portions:", diet)
    print("Scaled portions:", scaled_diet)
    print("Totals: {:.1f} kcal (Target: {}) | P: {:.1f}g (Target: {}) | C: {:.1f}g (Target: {}) | G: {:.1f}g (Target: {})".format(kcal, target_kcal, p, target_p, c, target_c, g, target_g))
    print()
