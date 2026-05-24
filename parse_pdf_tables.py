import pypdf
import re
import json

pdf_path = '/home/veronica/Descargas/Propmting/Trabajo Final/2023_guiaDMSAMFyC_cap07anexo10.pdf'
json_out_path = '/home/veronica/Descargas/Propmting/Trabajo Final/ucm_food_database.json'

print("Reading PDF...")
reader = pypdf.PdfReader(pdf_path)

food_database = []
skipped_lines = []

# Regex to match the food code (6 digits) followed by name and values
# Example: 010101 Arroz 1 364 9,4 0 6,7 81,6 ...
# We want: Code, Name, Calories (kcal), Proteins, Carbs, Fats, Fiber
pattern = re.compile(r'^(\d{6})\s+(.+?)\s+(\d+(?:,\d+)?)\s+(\d+(?:,\d+)?)\s+(\d+(?:,\d+)?)\s+(\d+(?:,\d+)?)\s+(\d+(?:,\d+)?)\s+(\d+(?:,\d+)?)\s+([\d,]+|Tr\.|___)')

def clean_val(val_str):
    if val_str in ('Tr.', '___', 'Tr', '_'):
        return 0.0
    val_str = val_str.replace(',', '.')
    try:
        return float(val_str)
    except ValueError:
        return 0.0

print("Parsing pages...")
for page_num in range(14, len(reader.pages)):
    text = reader.pages[page_num].extract_text()
    if not text:
        continue
    
    # ONLY parse pages that have the Macronutrientes table headers
    if "macronutrientes" not in text.lower() and "energía" not in text.lower():
        continue
        
    for line in text.split('\n'):
        line = line.strip()
        # Look for lines starting with a 6-digit food code
        match = re.match(r'^(\d{6})\s+(.+)$', line)
        if match:
            code = match.group(1)
            rest = match.group(2)
            
            parts = rest.split()
            numeric_start_idx = -1
            for idx in range(len(parts)):
                token = parts[idx]
                if re.match(r'^\d+(?:,\d+)?$', token) or token in ('Tr.', '___', 'Tr'):
                    subsequent = parts[idx:idx+6]
                    is_numeric_block = all(re.match(r'^\d+(?:,\d+)?$', t) or t in ('Tr.', '___', 'Tr', '0') for t in subsequent)
                    if is_numeric_block:
                        numeric_start_idx = idx
                        break
            
            if numeric_start_idx != -1:
                name = " ".join(parts[:numeric_start_idx])
                num_parts = parts[numeric_start_idx:]
                
                if len(num_parts) >= 8:
                    p_comestible = clean_val(num_parts[0])
                    kcal = clean_val(num_parts[1])
                    water = clean_val(num_parts[2])
                    alcohol = clean_val(num_parts[3])
                    proteins = clean_val(num_parts[4])
                    carbs = clean_val(num_parts[5])
                    
                    try:
                        fats = 0.0
                        fiber = 0.0
                        if len(num_parts) > 10:
                            fats = clean_val(num_parts[10])
                        if len(num_parts) > 9:
                            fiber = clean_val(num_parts[9])
                        
                        # Only add if it's the macro entry (avoid duplicates or overwrite if somehow duplicate)
                        # The macro entry always has non-trivial kcal (e.g. Arroz is 364, not 0.05)
                        food_database.append({
                            "code": code,
                            "name": name,
                            "kcal": kcal,
                            "proteins": proteins,
                            "carbs": carbs,
                            "fats": fats,
                            "fiber": fiber
                        })
                    except Exception as ex:
                        skipped_lines.append((line, str(ex)))
                else:
                    skipped_lines.append((line, "Too few numeric columns"))
            else:
                skipped_lines.append((line, "Could not find numeric values start"))

# Remove duplicates keeping the one with higher kcal (which corresponds to the macro table)
cleaned_db = {}
for item in food_database:
    code = item["code"]
    if code not in cleaned_db or item["kcal"] > cleaned_db[code]["kcal"]:
        cleaned_db[code] = item

final_db = list(cleaned_db.values())

print(f"Successfully parsed and cleaned {len(final_db)} foods!")
print(f"Skipped {len(skipped_lines)} lines.")

# Save to JSON
with open(json_out_path, 'w', encoding='utf-8') as f:
    json.dump(final_db, f, ensure_ascii=False, indent=2)

print("JSON saved to ucm_food_database.json.")
# Print a few samples
for item in final_db[:5]:
    print(item)
