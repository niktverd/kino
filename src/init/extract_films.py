#!/usr/bin/env python3

from __future__ import annotations

import argparse
import json
import re
import subprocess
from dataclasses import dataclass
from pathlib import Path


HEADER_RE = re.compile(r"^\[(?P<index>\d+)\] (?P<role>\w+)$")
YEAR_RE = re.compile(
    r"\((?:19|20)\d{2}(?:[–-](?:19|20)\d{2})?(?:,\s*(?:19|20)\d{2})*\)"
)
INLINE_STATUS_RE = re.compile(
    r"\s+-\s+(?:смотрел|посмотрели|класс|очень понрав|понрав|не понрав|"
    r"не сегодня|не буду|прикольно|жестко|туповат|даже не буду|в целом|"
    r"хороший кандидат|в прошлом году|староват)",
    re.IGNORECASE,
)
USER_LIST_HEADING_RE = re.compile(
    r"(смотрел|понравил|не понрав|очень понрав|уже видел|"
    r"запланировано|в закладках|класс|ориентир)",
    re.IGNORECASE,
)

DESCRIPTION_PREFIXES = (
    "почему:",
    "сюжет:",
    "о чем:",
    "что внутри:",
    "визуал:",
    "стиль:",
    "что нового:",
    "приключение:",
    "магия:",
    "монстры:",
    "детектив:",
    "расследование:",
    "точность:",
    "точность и детали:",
    "тонкости:",
    "тонкости и детали:",
    "тонкость и затейливость:",
    "элегантность:",
    "шахматная партия:",
    "интеллектуальная дуэль:",
    "для вас:",
    "для кого:",
    "для ребенка:",
    "для 10 лет:",
    "для подростков:",
    "природа:",
    "технологии:",
    "актеры:",
    "герои:",
    "фишка:",
    "атмосфера:",
    "место действия:",
    "экшен:",
    "связь с",
)

NON_TITLE_PREFIXES = (
    "если",
    "почему",
    "сюжет",
    "визуал",
    "вайб",
    "тонкости",
    "точность",
    "детектив",
    "элегантность",
    "шахматная партия",
    "интеллектуальная дуэль",
    "многоходовочка",
    "что внутри",
    "для вас",
    "для ребенка",
    "для 10 лет",
    "для подростков",
    "для кого",
    "монстры",
    "природа",
    "стиль",
    "настроение",
    "экшен",
    "расследование",
    "профессионалы",
    "связь с",
    "главная рекомендация",
    "вердикт",
    "о чем",
    "что нового",
    "приключение",
    "технологии",
    "актеры",
    "герои",
    "классика",
    "начните",
    "включайте",
    "смело включайте",
    "мой совет",
    "моя рекомендация",
    "с чего",
    "пусть",
    "не пугайтесь",
    "забудьте",
    "полностью",
    "отменяем",
    "теперь",
    "это",
    "вот",
    "раз ",
    "вы ",
    "вам ",
    "тебе ",
    "нам ",
    "какая",
    "как ",
    "жирный лайк",
    "порекомендуй",
    "подкинешь",
    "давай",
    "природа и приключения",
    "понял",
    "отличный вкус",
)

IGNORE_NAMES = {
    "Понял. Оценка «Мумии» (1999) «на троечку»",
    "Слишком страшный - Мег: Монстр глубины",
    "65 - выглядит скучновато",
    "Бордерлендс - вцелом гуд, но с ребенком 10 лет чтуток пошловат",
    "Джон Уик - слишком много жестокости",
    "Джунгли (2017) с Дэниелом Рэдклиффом",
    "А вот картинка мрачноватая. Убийство на ниле гораздо приятнее смотреть",
}

MANUAL_ALIASES = {
    "Гарри поттер": "Гарри Поттер",
    "Хоббит": "Хоббит (серия)",
    "Властелин Колец": "Властелин Колец (серия)",
    "Безумный макс": "Безумный Макс (серия)",
    "Джон картер": "Джон Картер (2012)",
    "Матрица": "Матрица (серия)",
    "Дюна": "Дюна",
    "Принц Персии Пески времени": "Принц Персии: Пески времени (2010)",
    "Анчартед: На картах не значится": "Анчартед: На картах не значится (2022)",
    "Валериан и город тысячи планет": "Валериан и город тысячи планет (2017)",
    "Грань будущего": "Грань будущего (2014)",
    "Варкрафт": "Варкрафт (2016)",
    "Меч короля Артура": "Меч короля Артура (2017)",
    "Стражи Галактики": "Стражи Галактики (трилогия)",
    "Kingsman": "Kingsman: Секретная служба (2014)",
    "Тихоокеанский рубеж": "Тихоокеанский рубеж (2013)",
    "Железный человек": "Железный человек (серия)",
    "Мстители": "Мстители (серия)",
    "Тор: Рагнарёк": "Тор: Рагнарёк (2017)",
    "Живая сталь (": "Живая сталь (2011)",
    "Топ Ган: Мэверик": "Топ Ган: Мэверик (2022)",
    "ОБливион": "Обливион",
    "Мумия с Томом крузом": "Мумия с Томом Крузом",
    "Перси Джексон и похититель молний": "Перси Джексон и похититель молний (2010)",
    "Конг: Остров черепа": "Конг: Остров черепа (2017)",
    "Трансформеры": "Трансформеры (серия)",
    "Я, робот": "Я, робот (2004)",
    "Джон Уик": "Джон Уик (2014)",
    "Круиз по джунглям": "Круиз по джунглям (2021)",
    "Аладдин": "Аладдин (2019)",
    "Главный герой": "Главный герой (2021)",
    "Вилли Вонка (2023)": "Вонка (2023)",
    "Вонка (2023)": "Вонка (2023)",
    "Белоснежка и Охотник 2": "Белоснежка и Охотник 2 (2016)",
    "Проект Адам": "Проект «Адам» (2022)",
    "Джон Картер": "Джон Картер (2012)",
    "Тролль": "Тролль (2022)",
    "Красное уведомление": "Красное уведомление (2021)",
    "King's Man: Начало": "King's Man: Начало (2021)",
    "Смерть на Ниле": "Смерть на Ниле (2022)",
    "Достать ножи": "Достать ножи (2019)",
    "Смотрите, как они бегут": "Смотрите, как они бегут (2022)",
    "Фокус": "Фокус (2015)",
    "Каскадеры": "Каскадеры (2024)",
    "Костюм": "Костюм (2022)",
    "Невидимый гость": "Невидимый гость (2016)",
    "Лучшее предложение": "Лучшее предложение (2013)",
    "Игра на вылет": "Игра на вылет (2007)",
    "Миссия не выполнима (все части)": "Миссия невыполнима (серия)",
    "Миссия невыполнима (серия)": "Миссия невыполнима (серия)",
    "Годзилла и Конг (вся серия) — пересмотрел всё про Конга, класс": "Годзилла и Конг (серия)",
    "Годзилла и Конг (вся серия) — пересмотрел всё, класс": "Годзилла и Конг (серия)",
    "Трансформеры (все фильмы) — посмотрели все, класс": "Трансформеры (серия)",
    "Трансформеры (вся серия) — посмотрели все, класс": "Трансформеры (серия)",
    "Джуманджи (вся серия) — посмотрели все, класс": "Джуманджи (серия)",
    "Джуманджи (вся серия) — посмотрели всё, класс": "Джуманджи (серия)",
    "Индиана Джонс (две последние части) — посмотрели, хорошо": "Индиана Джонс (две последние части)",
    "Индиана Джонс (две последние части) — хорошо": "Индиана Джонс (две последние части)",
    "Сокровище нации (две части) — смотрел, хорошо": "Сокровище нации (серия)",
    "Сокровище нации (1 и 2 части) — смотрел, хорошо": "Сокровище нации (серия)",
    "Шерлок Холмс (Гай Ричи) — эталон детективного боевика": "Шерлок Холмс (дилогия Гая Ричи)",
    "Шерлок Холмс (дилогия Гая Ричи) — эталон жанра": "Шерлок Холмс (дилогия Гая Ричи)",
    "Эркюль Пуаро — посмотрели три серии": "Эркюль Пуаро",
    "Железный человек (вся серия) — эталон харизматичного героя и красивых технологий": "Железный человек (серия)",
    "В потерянных землях (In the Lost Lands) — в закладках": "В потерянных землях (In the Lost Lands)",
    "Джуманджи: Зов джунглей (2017) (и вся серия)": "Джуманджи: Зов джунглей (2017)",
    "Годзилла и Конг: Новая империя (2024) (и все фильмы про Конга)": "Годзилла и Конг: Новая империя (2024)",
    "Трансформеры: Восхождение Звероботов (2023) (и вся серия)": "Трансформеры: Восхождение Звероботов (2023)",
    "47 ронинов - в целом не плохо, но скучновато": "47 ронинов (2013)",
}

FALLBACK_DESCRIPTIONS = {
    "Гарри Поттер": "Магическая приключенческая серия о юном волшебнике и борьбе со злом.",
    "Хоббит (серия)": "Фэнтезийные приключения о походе в Эребор, драконах и битвах за Средиземье.",
    "Властелин Колец (серия)": "Эпическое фэнтези о Кольце Всевластия, братстве и войне за Средиземье.",
    "Безумный Макс (серия)": "Постапокалиптические боевики о выживании, погонях и безумном мире пустошей.",
    "Матрица (серия)": "Фантастическая серия о виртуальной реальности, машинах и избранном герое.",
    "Миссия невыполнима (серия)": "Шпионская франшиза о высокотехнологичных операциях Итана Ханта.",
    "Железный человек (серия)": "Супергеройская серия о Тони Старке, технологиях и харизматичном герое.",
    "Мстители (серия)": "Командная супергероика Marvel о спасении мира и масштабных битвах.",
    "Джуманджи (серия)": "Приключенческая серия о героях, попадающих в опасный игровой мир.",
    "Трансформеры (серия)": "Блокбастеры о войне гигантских роботов на Земле.",
    "Сокровище нации (серия)": "Приключенческая серия о поиске исторических загадок и сокровищ.",
    "Шерлок Холмс (дилогия Гая Ричи)": "Стильные приключенческие детективы о Шерлоке Холмсе в версии Гая Ричи.",
    "Годзилла и Конг (серия)": "Серия о гигантских монстрах, эпических схватках и фантастических мирах.",
    "Индиана Джонс (две последние части)": "Поздние приключения Индианы Джонса с артефактами, ловушками и погонями.",
}

SLUG_REPLACEMENTS = str.maketrans(
    {
        "а": "a",
        "б": "b",
        "в": "v",
        "г": "g",
        "д": "d",
        "е": "e",
        "ё": "e",
        "ж": "zh",
        "з": "z",
        "и": "i",
        "й": "y",
        "к": "k",
        "л": "l",
        "м": "m",
        "н": "n",
        "о": "o",
        "п": "p",
        "р": "r",
        "с": "s",
        "т": "t",
        "у": "u",
        "ф": "f",
        "х": "kh",
        "ц": "ts",
        "ч": "ch",
        "ш": "sh",
        "щ": "shch",
        "ъ": "",
        "ы": "y",
        "ь": "",
        "э": "e",
        "ю": "yu",
        "я": "ya",
    }
)


@dataclass
class Message:
    index: int
    role: str
    text: str


@dataclass
class Mention:
    name: str
    description: str | None


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Extract film entries from the chat by reading print_messages.py in chunks."
    )
    parser.add_argument(
        "--printer",
        type=Path,
        default=Path(__file__).with_name("print_messages.py"),
        help="Path to print_messages.py.",
    )
    parser.add_argument(
        "--chunk-size",
        type=int,
        default=12,
        help="How many messages to read per chunk.",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path(__file__).with_name("films"),
        help="Directory for generated YAML files.",
    )
    return parser.parse_args()


def read_messages(printer: Path, chunk_size: int) -> list[Message]:
    messages: list[Message] = []
    start = 0

    while True:
        end = start + chunk_size - 1
        result = subprocess.run(
            [str(printer), str(start), str(end)],
            text=True,
            capture_output=True,
            check=False,
        )

        if result.returncode != 0:
            if "No messages matched the requested range." in result.stderr:
                break
            raise SystemExit(result.stderr.strip() or f"Failed to run {printer}")

        chunk = parse_chunk_output(result.stdout)
        if not chunk:
            break

        messages.extend(chunk)
        if len(chunk) < chunk_size:
            break

        start += chunk_size

    return messages


def parse_chunk_output(output: str) -> list[Message]:
    messages: list[Message] = []
    current_index: int | None = None
    current_role: str | None = None
    current_lines: list[str] = []

    for raw_line in output.splitlines():
        match = HEADER_RE.match(raw_line)
        if match:
            if current_index is not None and current_role is not None:
                messages.append(
                    Message(
                        index=current_index,
                        role=current_role,
                        text="\n".join(current_lines).strip(),
                    )
                )
            current_index = int(match.group("index"))
            current_role = match.group("role")
            current_lines = []
            continue

        if current_index is not None:
            current_lines.append(raw_line)

    if current_index is not None and current_role is not None:
        messages.append(
            Message(index=current_index, role=current_role, text="\n".join(current_lines).strip())
        )

    return messages


def strip_prefix(line: str) -> str:
    stripped = line.strip()
    stripped = re.sub(r"^\d+\.\s+", "", stripped)
    stripped = re.sub(r"^[-•]\s*", "", stripped)
    return stripped.strip()


def clean_spaces(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip()


def is_titleish(text: str) -> bool:
    value = clean_spaces(text)
    if not value:
        return False
    if len(value) > 90:
        return False
    if value.endswith((".", "!", "?", ":")):
        return False
    lowered = value.lower()
    if any(lowered.startswith(prefix) for prefix in NON_TITLE_PREFIXES):
        return False
    if not re.search(r"[A-Za-zА-Яа-я]", value):
        return False
    return True


def raw_title_candidate(line: str, *, user_list: bool) -> str | None:
    candidate = clean_spaces(strip_prefix(line))
    if not candidate or candidate in {"-", "—"}:
        return None

    candidate = INLINE_STATUS_RE.split(candidate, maxsplit=1)[0].strip()
    if not candidate:
        return None

    if " — " in candidate:
        left, right = candidate.rsplit(" — ", 1)
        if YEAR_RE.search(left):
            candidate = left.strip()
        elif re.fullmatch(r"[A-Za-z0-9 :!&.,'\-\(\)]+", right.strip()):
            candidate = left.strip()

    if not user_list and not YEAR_RE.search(candidate) and " — " not in line:
        return None

    if candidate in IGNORE_NAMES:
        return None

    if not is_titleish(candidate):
        return None

    return candidate


def description_from_line(line: str) -> str | None:
    stripped = clean_spaces(strip_prefix(line))
    lowered = stripped.lower()

    for prefix in DESCRIPTION_PREFIXES:
        if lowered.startswith(prefix):
            text = stripped.split(":", 1)[1].strip() if ":" in stripped else stripped
            return text or None

    return None


def extract_mentions(messages: list[Message]) -> list[Mention]:
    mentions: list[Mention] = []

    for message in messages:
        lines = message.text.splitlines()
        in_user_list = False

        for index, raw_line in enumerate(lines):
            line = raw_line.strip()
            if not line:
                in_user_list = False
                continue

            if message.role == "user" and USER_LIST_HEADING_RE.search(line):
                in_user_list = True
                continue

            title = raw_title_candidate(line, user_list=in_user_list)
            if not title:
                if in_user_list and not is_titleish(line):
                    in_user_list = False
                continue

            description: str | None = None
            if message.role == "assistant":
                for follow_index in range(index + 1, len(lines)):
                    follow_line = lines[follow_index].strip()
                    if not follow_line:
                        continue
                    if raw_title_candidate(follow_line, user_list=False):
                        break
                    description = description_from_line(follow_line)
                    if description:
                        break

            mentions.append(Mention(name=title, description=description))

    return mentions


def simplify_base(name: str) -> str:
    base = re.sub(r"\((?:19|20)\d{2}(?:[–-](?:19|20)\d{2})?(?:,\s*(?:19|20)\d{2})*\)", "", name)
    base = clean_spaces(base.replace("ё", "е").casefold())
    return base


def apply_manual_alias(name: str) -> str:
    return MANUAL_ALIASES.get(name, name)


def normalize_name(name: str, base_map: dict[str, str]) -> str:
    normalized = apply_manual_alias(name.strip())

    if normalized in MANUAL_ALIASES:
        normalized = MANUAL_ALIASES[normalized]

    if normalized in IGNORE_NAMES:
        return ""

    base = simplify_base(normalized)
    if normalized == name and base in base_map:
        normalized = base_map[base]

    return normalized.strip()


def resolve_base_map(names: list[str]) -> dict[str, str]:
    candidates: dict[str, list[str]] = {}
    for name in names:
        fixed = apply_manual_alias(name)
        base = simplify_base(fixed)
        candidates.setdefault(base, []).append(fixed)

    mapping: dict[str, str] = {}
    for base, options in candidates.items():
        unique = list(dict.fromkeys(options))
        if len(unique) == 1:
            mapping[base] = unique[0]
            continue

        year_options = [item for item in unique if YEAR_RE.search(item)]
        if len(year_options) == 1:
            mapping[base] = year_options[0]
            continue

        trilogy_or_series = [
            item
            for item in unique
            if any(token in item.lower() for token in ("серия", "трилогия", "дилогия"))
        ]
        if len(trilogy_or_series) == 1:
            mapping[base] = trilogy_or_series[0]
            continue

        mapping[base] = sorted(unique, key=len)[0]

    return mapping


def merge_mentions(mentions: list[Mention]) -> dict[str, str | None]:
    base_map = resolve_base_map([mention.name for mention in mentions])
    merged: dict[str, str | None] = {}

    for mention in mentions:
        name = normalize_name(mention.name, base_map)
        if not name:
            continue

        description = mention.description
        if description:
            description = clean_spaces(description)

        if name not in merged:
            merged[name] = description
            continue

        if not merged[name] and description:
            merged[name] = description

    for name, description in list(merged.items()):
        if description:
            continue
        if name in FALLBACK_DESCRIPTIONS:
            merged[name] = FALLBACK_DESCRIPTIONS[name]

    return dict(sorted(merged.items(), key=lambda item: item[0].casefold()))


def slugify(name: str) -> str:
    lowered = name.lower().translate(SLUG_REPLACEMENTS)
    lowered = lowered.replace("&", " and ")
    lowered = re.sub(r"[^a-z0-9]+", "-", lowered)
    lowered = re.sub(r"-{2,}", "-", lowered).strip("-")
    return lowered or "film"


def yaml_line(key: str, value: str) -> str:
    return f"{key}: {json.dumps(value, ensure_ascii=False)}\n"


def write_yaml_files(records: dict[str, str | None], output_dir: Path) -> int:
    output_dir.mkdir(parents=True, exist_ok=True)
    for existing in output_dir.glob("*.yaml"):
        existing.unlink()

    used_slugs: set[str] = set()

    count = 0
    for name, description in records.items():
        slug = slugify(name)
        original_slug = slug
        suffix = 2
        while slug in used_slugs:
            slug = f"{original_slug}-{suffix}"
            suffix += 1
        used_slugs.add(slug)

        target = output_dir / f"{slug}.yaml"
        content = yaml_line("name", name)
        if description:
            content += yaml_line("description", description)
        target.write_text(content, encoding="utf-8")
        count += 1

    return count


def main() -> int:
    args = parse_args()
    messages = read_messages(args.printer, args.chunk_size)
    mentions = extract_mentions(messages)
    records = merge_mentions(mentions)
    count = write_yaml_files(records, args.output_dir)
    print(f"Wrote {count} YAML files to {args.output_dir}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
