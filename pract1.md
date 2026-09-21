## Задание 1
Ответ: grep -o "^[^:]*" passwd 
  1) "-" флаг
  2) o - вывод только той части которая совпала, а не всей строки
  3) "^[^:]*" - регулярное выражение (^ - искать с начала слова, [^:] - любой символ кроме :, * - ноль или больше символов)
  4) passwd - путь к папке/файлу

## Задание 2
Ответ: awk '!/^#/ && NF {print $2, $1}' protocols | sort -rn | head -5
  1) awk - читает файл построчно
  2) ' ' вместо " ", чтобы не выполнялся !
  3) !/^#/ - строка не начинается с "#"
  4) NF - печатает только непустые строки
  5) {print $2, $1} - печатает сначала 2 столбец, потом 1 столбец, "," - разделитель в выводе (пробел)
  6) protocols - путь к файлу из текущей директории
  7) "|" - конвейер
  8) sort - сортировка, -r - инвертированная, -n - сортировка по числам
  9) head - вывести первые N строк, -N - кол-во строк

## Задание 3
Ответ:
#!/usr/bin/env bash

text="${1:-}"
len=${#text}
border="+"

for ((i=0; i < len + 2; i++)); do
border+="-"

border+="+"

printf "%s\n" "$border"
printf "| %s |\n" "$text"
printf "%s\n" "$border"

done

## Задание 4
Ответ:
#!/usr/bin/env bash

file="${1 :?Usage: $0 FILE}"

grep -o '[A-Za-z_][A-Za-z0-9_]*' "$file" | sort -u

1) sort -u - убирает дубликаты (u - unique)
2) grep -o - выводит только совпадения

## Задание 5
Ответ:
#!/usr/bin/env bash

set -eou pipefail

name="${1:?Usage: $0 FILE}"

if [[ ! -f "$name" ]]; then
  echo "Ошибка: '$name' не найден" >&2
  exit 1

fi

if [[ "$(head -c 2 "$name")" != "#!" ]]; then
  echo "Ошибка: '#name' не является скриптом (нет #!)" >&2
  exit 1

fi

chmod 755 "$name"

dest="/usr/local/bin/$ (basename "$name")"
cp "$name" "$dest"
chmod 755 "$dest"

echo "OK: $name -> $dest (755)"


## Задание 6
Ответ:
#!/usr/bin/env bash

set -euo pipefail

dir="${1:-.}"

if [[ ! -d "$dir" ]]; then
  echo "Ошибка: '$dir' не каталог" >&2
  exit 1
fi

while IFS= read -r -d '' file; do
  IFS= read -r first < "$file" || first=""

  ext="${file## *. }"
  has comment=0

  case "$ext" in
    c|js)
      if [[ "$first" =~ ^[[:space:]]*(//|/\*) ]]; then
        has_comment=1
      fi
      ;;
    py)
      if [[ "$first" =~ ^[[:space: ]]*# ]]; then
        has_comment=1
      fi
      ;;
  esac

  if (( has_comment )); then
    echo "OK $file"
  else
    echo "NO $file"
  fi

done < <(find "$dir" -type f \( -name '*.c' -o -name '*.js' -o -name '*.py' \) -print0)

## Задание 7
Ответ:


## Задание 8
Ответ:


## Задание 9
Ответ:


## Задание 10
Ответ:


