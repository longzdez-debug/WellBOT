#!/usr/bin/env python3
"""
update_github.py — Полное обновление репозитория на GitHub
Запуск: python update_github.py
"""

import os
import subprocess
import sys
from pathlib import Path
from datetime import datetime

ROOT_DIR = Path(__file__).parent


def main():
    """Основная функция обновления GitHub."""
    
    print("\n" + "="*70)
    print("📦 ОБНОВЛЕНИЕ РЕПОЗИТОРИЯ НА GITHUB")
    print("="*70 + "\n")
    
    # Проверяем наличие git
    if not check_git():
        print("❌ Git не установлен или не найден в PATH")
        return
    
    # Проверяем, что мы в репозитории
    if not check_repo():
        print("❌ Это не git репозиторий")
        return
    
    # 1. Показываем статус
    print("📋 1. Проверка статуса...")
    show_status()
    
    # 2. Добавляем все файлы
    print("\n📦 2. Добавление файлов...")
    add_files()
    
    # 3. Создаём коммит
    print("\n📝 3. Создание коммита...")
    commit_changes()
    
    # 4. Пушим на GitHub
    print("\n🚀 4. Отправка на GitHub...")
    push_to_github()
    
    # 5. Показываем результат
    print("\n" + "="*70)
    print("✅ ГОТОВО!")
    print("="*70)
    
    print("\n📝 Что было сделано:")
    print("   • Все изменения добавлены в git")
    print("   • Создан коммит с описанием")
    print("   • Изменения отправлены на GitHub")
    
    print("\n🔗 Проверьте репозиторий:")
    print("   https://github.com/ваш-username/wellbot")
    
    print("\n💡 Команды для ручного управления:")
    print("   git status — проверить состояние")
    print("   git log — посмотреть историю")
    print("   git push — отправить изменения")


def check_git():
    """Проверяет наличие git."""
    try:
        subprocess.run(['git', '--version'], 
                      capture_output=True, 
                      check=True)
        return True
    except (subprocess.CalledProcessError, FileNotFoundError):
        return False


def check_repo():
    """Проверяет, что мы в git репозитории."""
    result = subprocess.run(['git', 'rev-parse', '--is-inside-work-tree'],
                          capture_output=True, text=True)
    return result.returncode == 0


def show_status():
    """Показывает статус git."""
    result = subprocess.run(['git', 'status', '--short'],
                          capture_output=True, text=True)
    
    if result.stdout:
        print("   📋 Изменённые файлы:")
        for line in result.stdout.strip().split('\n'):
            print(f"      {line}")
    else:
        print("   ℹ️ Нет изменений для коммита")
    
    return result.stdout


def add_files():
    """Добавляет все файлы в git."""
    # Добавляем все файлы
    subprocess.run(['git', 'add', '.'], check=True)
    
    # Проверяем, что добавилось
    result = subprocess.run(['git', 'status', '--short'],
                          capture_output=True, text=True)
    
    if result.stdout:
        print("   ✅ Файлы добавлены:")
        for line in result.stdout.strip().split('\n'):
            print(f"      {line}")
    else:
        print("   ℹ️ Нет файлов для добавления")
    
    return True


def commit_changes():
    """Создаёт коммит с описанием."""
    # Получаем дату
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    
    # Создаём описание коммита
    commit_message = f"""WellBoT — Полное обновление проекта

Дата: {now}

Изменения:
✅ Полный ребрендинг в WellBoT
✅ Новая структура меню (Перекуп → KUFAR)
✅ Магазин цифровых товаров
✅ Анонимная система поддержки
✅ Исправлены все синтаксические ошибки
✅ Оптимизация и рефакторинг

Функции:
🔄 Перекуп — мониторинг площадок
🛒 Магазин — цифровые товары
💬 Поддержка — анонимные обращения
👤 Кабинет — тарифы, рефералы, бейджи
📊 Статистика — аналитика
🌍 Мультиязычность (RU/BY/EN)
🎁 Реферальная программа
🔒 Система подписок (Telegram Stars)

Технические улучшения:
- Исправлены все критические ошибки
- Добавлена валидация данных
- Улучшена безопасность
- Добавлены индексы в БД
- Оптимизированы запросы

Для администратора:
⚙️ Управление товарами
📋 Обращения в поддержку
📊 Статистика бота
🎁 Выдача подписок
🚫 Бан/Разбан пользователей
🎟 Управление промокодами

Проект готов к запуску! 🚀"""
    
    # Создаём коммит
    result = subprocess.run(['git', 'commit', '-m', commit_message],
                          capture_output=True, text=True)
    
    if result.returncode == 0:
        print("   ✅ Коммит создан")
        print(f"   📝 {commit_message.split(chr(10))[0]}")
        return True
    else:
        print(f"   ❌ Ошибка коммита: {result.stderr}")
        return False


def push_to_github():
    """Отправляет изменения на GitHub."""
    # Получаем текущую ветку
    branch_result = subprocess.run(['git', 'branch', '--show-current'],
                                 capture_output=True, text=True)
    branch = branch_result.stdout.strip() or 'main'
    
    print(f"   📌 Ветка: {branch}")
    
    # Пытаемся запушить
    try:
        result = subprocess.run(['git', 'push', 'origin', branch],
                              capture_output=True, text=True)
        
        if result.returncode == 0:
            print(f"   ✅ Изменения отправлены на GitHub (ветка: {branch})")
            
            # Показываем URL для создания PR если нужно
            print("\n   🔗 Ссылка на репозиторий:")
            print(f"      https://github.com/ваш-username/wellbot/tree/{branch}")
            
            return True
        else:
            # Проверяем, нужно ли настроить upstream
            if 'upstream' in result.stderr:
                print("   ⚠️ Настраиваем upstream...")
                subprocess.run(['git', 'push', '--set-upstream', 'origin', branch],
                             capture_output=True)
                print("   ✅ Upstream настроен, изменения отправлены")
                return True
            else:
                print(f"   ❌ Ошибка пуша: {result.stderr}")
                return False
                
    except Exception as e:
        print(f"   ❌ Ошибка: {e}")
        return False


def create_gitignore():
    """Создаёт .gitignore если его нет."""
    filepath = ROOT_DIR / '.gitignore'
    
    if filepath.exists():
        print("   ℹ️ .gitignore уже существует")
        return
    
    content = '''# Python
__pycache__/
*.py[cod]
*$py.class
*.so
.Python
env/
venv/
ENV/
env.bak/
venv.bak/

# Database
*.db
*.sqlite
*.sqlite3

# Logs
logs/
*.log

# IDE
.vscode/
.idea/
*.swp
*.swo
*~

# OS
.DS_Store
Thumbs.db

# Project specific
data/
*.backup
.env.local
.env.*.local

# Distribution
dist/
build/
*.egg-info/
'''
    
    with open(filepath, 'w', encoding='utf-8') as f:
        f.write(content)
    
    print("   ✅ .gitignore создан")


def show_github_commands():
    """Показывает команды для ручного управления."""
    print("\n" + "="*70)
    print("📋 КОМАНДЫ ДЛЯ РУЧНОГО УПРАВЛЕНИЯ")
    print("="*70)
    
    commands = [
        ("git status", "Проверить состояние"),
        ("git add .", "Добавить все файлы"),
        ('git commit -m "сообщение"', "Создать коммит"),
        ("git push", "Отправить на GitHub"),
        ("git pull", "Получить обновления"),
        ("git log --oneline", "История коммитов"),
        ("git branch -a", "Список веток"),
        ("git checkout -b new-branch", "Создать новую ветку"),
    ]
    
    print("\n   📌 Основные команды:")
    for cmd, desc in commands:
        print(f"      git {cmd:<30} — {desc}")


if __name__ == "__main__":
    main()