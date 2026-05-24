# -*- coding: utf-8 -*-
import json
import random

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

# Target: 2148 kcal, 165g P, 203g C, 75g G
target_kcal = 2148
target_p = 165
target_c = 203
target_g = 75

days_ingredients = {
    "Lunes": ["avena", "clara", "huevo", "pechuga_pollo", "arroz_integral", "aceite", "platano", "whey"],
    "Martes": ["pan_integral", "clara", "huevo", "ternera_magra", "pasta_integral", "aceite", "platano", "nuez"],
    "Miércoles": ["avena", "clara", "huevo", "pechuga_pollo", "patata_nueva", "aceite", "platano", "whey"],
    "Jueves": ["pan_integral", "clara", "huevo", "ternera_magra", "arroz_integral", "aceite", "platano", "nuez"],
    "Viernes": ["avena", "clara", "huevo", "pechuga_pollo", "pasta_integral", "aceite", "platano", "whey"],
    "Sábado": ["pan_integral", "clara", "huevo", "ternera_magra", "patata_nueva", "aceite", "platano", "nuez"],
    "Domingo": ["avena", "clara", "huevo", "pechuga_pollo", "arroz_integral", "aceite", "platano", "whey"]
}

for day, ing_list in days_ingredients.items():
    best_diet = None
    best_error = 999999
    
    # Try 100,000 random combinations of portions
    for _ in range(200000):
        diet = {}
        for ing in ing_list:
            # Set ranges depending on ingredient type to keep recipes logical
            if ing == "huevo":
                diet[ing] = 100 # always 2 eggs
            elif ing == "whey":
                diet[ing] = random.choice([0, 25, 30, 50])
            elif ing == "nuez":
                diet[ing] = random.choice([15, 20, 25, 30])
            elif ing == "platano":
                diet[ing] = random.choice([100, 120, 150])
            elif ing == "aceite":
                diet[ing] = random.randint(15, 35)
            elif ing in ["clara"]:
                diet[ing] = random.randint(150, 400)
            elif ing in ["pechuga_pollo", "ternera_magra"]:
                diet[ing] = random.randint(200, 400)
            elif ing in ["arroz_integral", "pasta_integral", "avena"]:
                diet[ing] = random.randint(50, 200)
            elif ing == "patata_nueva":
                diet[ing] = random.randint(200, 500)
            elif ing == "pan_integral":
                diet[ing] = random.randint(50, 150)
                
        kcal, p, c, g, fib = calc(diet)
        
        # Calculate weighted error (protein and carbs are important, fats are crucial, kcal is overall)
        err = abs(kcal - target_kcal) + abs(p - target_p)*4 + abs(c - target_c)*4 + abs(g - target_g)*8
        if err < best_error:
            best_error = err
            best_diet = (diet, kcal, p, c, g, fib)
            
    diet, kcal, p, c, g, fib = best_diet
    print(f"=== {day} ===")
    print("Portions:", {k: int(v) for k, v in diet.items()})
    print("Totals: {:.1f} kcal | P: {:.1f}g | C: {:.1f}g | G: {:.1f}g | F: {:.1f}g".format(kcal, p, c, g, fib))
    print()
