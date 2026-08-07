import os

output_file = 'project_code.txt'
ignore_dirs = {'__pycache__', 'logs', 'data', 'venv', '.git'}
allowed_extensions = {'.py', '.md', 'requirements.txt'}

with open(output_file, 'w', encoding='utf-8') as outfile:
    for root, dirs, files in os.walk('.'):
        dirs[:] = [d for d in dirs if d not in ignore_dirs]

        for file in files:
            if file.endswith(tuple(allowed_extensions)) or file == 'requirements.txt':
                filepath = os.path.join(root, file)

                if file == 'gather_code.py':
                    continue

                outfile.write(f"\n\n{'='*50}\n")
                outfile.write(f"ФАЙЛ: {filepath}\n")
                outfile.write(f"{'='*50}\n\n")

                try:
                    with open(filepath, 'r', encoding='utf-8') as infile:
                        outfile.write(infile.read())
                except Exception as e:
                    outfile.write(f"# Ошибка чтения: {e}\n")

print(f"Готово! Все файлы собраны в {output_file}")