# -*- coding: utf-8 -*-
import json

with open('ucm_food_database.json', 'r', encoding='utf-8') as f:
    db = {item['name'].lower(): item for item in json.load(f)}

# Let's map some short keys for convenience
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

# Add whey protein isolate manually as a sport supplement since it's not always in raw UCM files
foods["whey"] = {"kcal": 360.0, "proteins": 80.0, "carbs": 3.0, "fats": 2.0, "fiber": 0.0}

def calc_diet(items):
    total_kcal = 0
    total_p = 0
    total_c = 0
    total_g = 0
    total_f = 0
    for name, grams in items.items():
        food = foods[name]
        total_kcal += (food["kcal"] * grams / 100.0)
        total_p += (food["proteins"] * grams / 100.0)
        total_c += (food["carbs"] * grams / 100.0)
        total_g += (food["fats"] * grams / 100.0)
        total_f += (food["fiber"] * grams / 100.0)
    return {
        "kcal": round(total_kcal, 1),
        "proteins": round(total_p, 1),
        "carbs": round(total_c, 1),
        "fats": round(total_g, 1),
        "fiber": round(total_f, 1)
    }

# Let's design 7 days of menus targeting: 2148 kcal, 165g P, 75g G, 203g C
# Lunes
lunes = {
    "avena": 80,             # 282.4 kcal, 9.36g P, 44.56g C, 5.68g G, 7.76g Fib
    "clara": 250,            # 122.5 kcal, 27.75g P, 1.75g C, 0.5g G
    "huevo": 100,            # 162 kcal, 12.7g P, 0.68g C, 12.1g G
    "pechuga_pollo": 280,    # 406 kcal, 62.16g P, 0g C, 17.36g G
    "arroz_integral": 120,   # 420 kcal, 8.76g P, 88.92g C, 2.64g G
    "aceite": 22,            # 197.8 kcal, 0g P, 0g C, 22.0g G
    "platano": 100,          # 95.2 kcal, 1.1g P, 20.8g C, 0.27g G
    "whey": 50               # 180 kcal, 40.0g P, 1.5g C, 1.0g G
}

print("Lunes:", calc_diet(lunes))

# Let's adjust amounts to hit targets:
# Target: 2148 kcal, 165 P, 75 G, 203 C
# Let's see: Lunes totals:
# kcal = 282.4 + 122.5 + 162 + 406 + 420 + 197.8 + 95.2 + 180 = 1865.9 kcal. We need more calories.
# Let's adjust Lunes:
lunes_opt = {
    "avena": 100,            # 353 kcal, 11.7 P, 55.7 C, 7.1 G
    "clara": 300,            # 147 kcal, 33.3 P, 2.1 C, 0.6 G
    "huevo": 100,            # 162 kcal, 12.7 P, 0.68 C, 12.1 G
    "pechuga_pollo": 350,    # 507.5 kcal, 77.7 P, 0 C, 21.7 G
    "arroz_integral": 140,   # 490 kcal, 10.22 P, 103.74 C, 3.08 G
    "aceite": 24,            # 215.8 kcal, 0 P, 0 C, 24.0 G
    "platano": 120,          # 114.2 kcal, 1.32 P, 24.96 C, 0.32 G
    "whey": 25               # 90 kcal, 20.0 P, 0.75 C, 0.5 G
}
print("Lunes Opt:", calc_diet(lunes_opt))

# Martes
martes = {
    "pan_integral": 120,      # 310.8 kcal, 13.08 P, 52.8 C, 3.6 G
    "clara": 350,             # 171.5 kcal, 38.85 P, 2.45 C, 0.7 G
    "huevo": 100,             # 162 kcal, 12.7 P, 0.68 C, 12.1 G
    "ternera_magra": 300,     # 393 kcal, 62.1 P, 0 C, 16.2 G
    "pasta_integral": 120,    # 422.4 kcal, 15.72 P, 76.44 C, 3.48 G
    "aceite": 26,             # 233.7 kcal, 0 P, 0 C, 26.0 G
    "platano": 130,           # 123.8 kcal, 1.43 P, 27.04 C, 0.35 G
    "nuez": 20                # 129.8 kcal, 2.88 P, 0.88 C, 12.5 G
}
print("Martes:", calc_diet(martes))

# Miércoles
miercoles = {
    "avena": 110,
    "clara": 300,
    "huevo": 100,
    "pechuga_pollo": 320,
    "patata_nueva": 450,       # 331.2 kcal, 10.35 P, 66.6 C, 0.5 G
    "aceite": 26,
    "platano": 120,
    "whey": 30
}
print("Miércoles:", calc_diet(miercoles))

# Jueves
jueves = {
    "pan_integral": 140,
    "clara": 300,
    "huevo": 100,
    "ternera_magra": 280,
    "arroz_integral": 140,
    "aceite": 25,
    "platano": 100,
    "nuez": 25
}
print("Jueves:", calc_diet(jueves))

# Viernes
viernes = {
    "avena": 90,
    "clara": 350,
    "huevo": 100,
    "pechuga_pollo": 350,
    "pasta_integral": 110,
    "aceite": 24,
    "platano": 130,
    "whey": 20
}
print("Viernes:", calc_diet(viernes))

# Sábado
sabado = {
    "pan_integral": 100,
    "clara": 350,
    "huevo": 100,
    "ternera_magra": 320,
    "patata_nueva": 400,
    "aceite": 25,
    "platano": 150,
    "nuez": 15
}
print("Sábado:", calc_diet(sabado))

# Domingo
domingo = {
    "avena": 120,
    "clara": 300,
    "huevo": 100,
    "pechuga_pollo": 330,
    "arroz_integral": 120,
    "aceite": 24,
    "platano": 100,
    "whey": 25
}
print("Domingo:", calc_diet(domingo))
