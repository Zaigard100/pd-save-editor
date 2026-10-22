# Редактор сохранений Pacific Drive

Игра: Pacific Drive (внутреннее имя `PenDriverPro`), Unreal Engine 4, сборка `1.15.0-CL34030`.
Сохранения: `%LOCALAPPDATA%\PenDriverPro\Saved\SaveGames\odsaveN.sav`
(под Proton: `.../compatdata/<appid>/pfx/drive_c/users/steamuser/AppData/Local/PenDriverPro/...`).

> **⚠ Внимание.** Это неофициальный фанатский редактор. Некоторые функции могут сломать сохранение —
> **обязательно сделайте резервную копию**, если сохранения вам дороги. Относительно безопасно: выдавать себе
> предметы, редактировать предметы (прочность, заряды, эффекты), менять энергию якорей и открывать записи журнала.
> Всё остальное лучше делать внутри игры. А ещё лучше — честно пройти игру самому: так прокачка и сама игра
> принесут больше удовольствия, а с редактором можно поиграться после прохождения, когда машина покрыта олимпием
> и стоят топовые модули, — для фана и экспериментов.
>
> Редактор проверен на **Pacific Drive 1.15.0 (сборка 245)**. Обновления игры могут изменить формат сохранений и
> упаковку игровых файлов — на других версиях стабильная работа не гарантируется.
>
> Pacific Drive — игра Ironwood Studios; редактор с разработчиками не связан. © 2026,
> [github.com/Zaigard100/pd-save-editor](https://github.com/Zaigard100/pd-save-editor). Спасибо, что пользуетесь!

Нужен только Python 3.8+ (для GUI ещё tkinter). Сторонних зависимостей нет, LZ4 реализован внутри.

## Скачать и запустить

Готовые сборки — на странице **Releases**:

* Windows: `PDSaveEditor-windows-x64.exe` — просто запустить.
* Linux: `PDSaveEditor-x86_64.AppImage` — сделать исполняемым (`chmod +x`) и запустить двойным
  кликом или из терминала. Без терминала редактор закрывается кнопкой «Выход».

Откроется окно-консоль и вкладка браузера с редактором (http://127.0.0.1:8765/).
Закрыть — кнопка «Выход» в редакторе или закрыть консоль.

При **первом запуске** редактор сам находит установленную игру (библиотеки Steam на Windows и Linux,
Proton) и извлекает из её .pak-файлов названия на 14 языках, иконки, раскладки контейнеров, пресеты,
меню настроек, дерево исследований и журнал. Эти данные хранятся только у вас:
`%APPDATA%\PDSaveEditor` (Windows) или `~/.local/share/pdsave-editor` (Linux). В сборке редактора
ресурсов игры нет. Если игра не найдена — укажите её папку вручную.

Сохранения ищутся в `%LOCALAPPDATA%\PenDriverPro\Saved\SaveGames` (Windows) и в префиксе Proton
(`steamapps/compatdata/1458140/...`) на Linux; другую папку можно выбрать кнопкой «Папка…».
Перед каждой записью рядом создаётся `odsaveN.sav.bak-ДАТА`. Закройте игру перед правкой;
Steam Cloud может заменить файл облачной версией.

Вкладки: Инвентарь (все контейнеры: багажник, рюкзак, крепления на машине, хранилища гаража,
стеллажи деталей, пневмопочта, станции, рамки), Автомобиль (детали, ремонт, покраска, эффекты,
парадоксы), Исследования (дерево как в игре + «почему недоступно»), Журнал, Энергия и ресурсы,
Статистика, Настройки игры (пресеты + переопределения), Сводка.

## Запуск из исходников и сборка

```
pip install pillow
python3 pdedit_web.py [папка_SaveGames или odsaveN.sav]      # первый запуск предложит извлечь данные
python3 extract/build_gamedata.py "/путь/к/Pacific Drive"   # или извлечь вручную в ./gamedata
python3 -m unittest discover -s tests                        # тесты кодека
pip install pyinstaller && pyinstaller --noconfirm PDSaveEditor.spec   # один файл в dist/
PDSAVE_ONEDIR=1 pyinstaller --noconfirm PDSaveEditor.spec && packaging/linux/build_appimage.sh   # AppImage
```

Сборка релизов: GitHub Actions (`.github/workflows/build.yml`) на каждый тег `v*` гоняет тесты,
собирает Windows-версию (`.exe`) и Linux-версию (AppImage) PyInstaller'ом и публикует их в Releases.

## Командная строка и старый GUI

```
python3 pdedit_gui.py [odsave2.sav]          # GUI: дерево, поиск, правка, быстрые валюты/ресурсы

python3 pdedit.py info      odsave2.sav
python3 pdedit.py currency  odsave2.sav MechXP=500000 AnchorJuice_Stable=999
python3 pdedit.py resource  odsave2.sav Fuel=75 CarHealth=795
python3 pdedit.py find      odsave2.sav 'MaxRevealCharges|Durability'
python3 pdedit.py get       odsave2.sav GAME/managers/_objects/<GUID>/_data
python3 pdedit.py set       odsave2.sav GAME/managers/_objects/<GUID>/_data/MaxRevealCharges 8
python3 pdedit.py inventory odsave2.sav                    # список контейнеров
python3 pdedit.py inventory odsave2.sav Inventory_Trunk    # слоты контейнера
python3 pdedit.py additems  odsave2.sav <SLOT_GUID> 10     # клонировать предмет слота
python3 pdedit.py export    odsave2.sav dump.json          # полный JSON без потерь
python3 pdedit.py import    dump.json odsave2.sav          # и обратно
```

Каждая запись сначала собирает файл, перечитывает и проверяет его, потом кладёт рядом
`odsave2.sav.bak-ГГГГММДД-ЧЧММСС`. Опции записи: `--no-backup`, `--no-compress`, `--dry-run`.

Пути: `ТЕГ/поле/поле/...`. В структурах шаг — имя поля (суффикс типа `|I` можно не писать),
в массивах — индекс, в map — текст ключа или `#индекс` (ключи обычно пути ассетов со `/`).

**Перед правкой:** закройте игру. Включён Steam Cloud (`steam_autocloud.vdf`), он может
перезаписать изменённый файл облачной версией — правьте при выключенной синхронизации
или проверьте, что Steam загрузил именно ваш файл.

## Формат файла

### Контейнер `SAVC` (little-endian)

| смещение | тип | значение |
|---|---|---|
| 0x00 | char[4] | `SAVC` |
| 0x04 | u32 | версия контейнера = 1 |
| 0x08 | u8[8] | нули |
| 0x10 | 16 × 24 байта | таблица секций |

Запись таблицы: `char[4] tag, u32 offset, u32 slot, u32 size, u32 format, u32 rawsize`.
Секции лежат подряд (`next.offset = offset + slot`), неиспользуемые записи нулевые
с `offset` = конец данных. Контрольных сумм нет.

* `format`: 1 = JSON-текст (сейвы 2024 г., слот кратен 4096, хвост слота — мусор старого буфера),
  2 = бинарный, 6 = бинарный + LZ4 block (`rawsize` = размер после распаковки).
  Игра сама пишет 2, если сжатие не уменьшило размер («Skip writing compressed section ...
  compressed data is larger»), так что несжатый GAME допустим.
* Секции: `OPTS` (настройки/пресет сложности, `DrivingGameUserSettings`), `META`
  (превью для меню загрузки: дата, время игры, миссия, кэш статов машины), `GAME` (весь мир),
  `CHKP` (чекпоинт, во всех образцах пуст).

### Полезная нагрузка (сериализатор «Fig», плагин `PDFeature_Fig`)

`u32 6, u32 3` (заголовок; в JSON-варианте `"_version": 3`), затем `type value` корня.

Тип — байт-код, у контейнеров следом идут дескрипторы элементов. Буквы — собственная
таблица игры, строка `-BIFSNXVRQZCLGTD:^$AM*>#E@~` в exe, индексируется кодом:

| код | буква | значение | кодирование |
|---|---|---|---|
| 01 | B | bool | u32 0/1 |
| 02 | I | int32 | |
| 03 | F | float | float32 |
| 04 | S | FString | i32 len (с NUL; <0 → UTF‑16, len символов) |
| 05 | N | FName | как FString |
| 06 | X | FText | нативная UE‑сериализация FText (flags, history…); в JSON — base64 |
| 07 | V | FVector | 3×f32 (в образцах не встречен) |
| 08 | R | FRotator | 3×f32 |
| 09 | Q | FQuat | 4×f32 (не встречен) |
| 0A | Z | FTransform | 10×f32: quat xyzw, позиция, масштаб |
| 0B | C | FColor | 4×u8 (не встречен) |
| 0C | L | FLinearColor | 4×f32 |
| 0D | G | FGuid | 16 байт = 4×u32, печатается `%08X`×4 |
| 0E | T | GameplayTag | FString |
| 0F | D | FDateTime | int64 тики по 100 нс с 0001‑01‑01 |
| 10 | : | struct | u32 n, n×(FString имя, type, value) |
| 11 | ^ | путь класса | FString |
| 12 | $ | ссылка на объект | u8 kind: 0 null; 1 class+GUID (`@`); 2 class+имя (`$__GAMEINSTANCE__`); 3 class+путь ассета (`*`) |
| 13 | A | array | `13 elemtype`, u32 n, значения |
| 14 | M | map | `14 keytype valtype`, u32 n, u32 n, все ключи, затем все значения |
| 15 | * | динамическая структура | как `:` |
| 16 | > | запись объекта | как `:`, поля `_class _name _outer _data [_components _transform …]` |
| 17 | # | blob | u32 len + байты (JPEG-снимки бортжурнала) |
| 18 | E | int64 | |
| 19 | @ | soft object path | FString |
| 1A | ~ | soft class path | FString |

В JSON редактора поле записывается как `"Имя|ТИП": значение`, ссылки — как
`"@GUID|класс"`, `"$имя|класс"`, `"*путь|класс"` (тот же вид, что в JSON-сейвах самой игры).
Map выводится списком пар `[ключ, значение]`.

### Что где лежит в GAME

* `managers/_data` — 30 менеджеров (`BP_*Manager_C`), `managers/_objects` — ~15 тыс. объектов
  по GUID; `Garage/_objects` — сцена гаража; `hashes` — отпечатки схем классов
  (`_typehash`, `_numproperties`, …), видимо для проверки совместимости при загрузке.
* Валюты: `BP_InventoryManager_C._data.CurrencyTable` (map ассет `CA_*` → int64):
  `CA_AnchorJuice_Stable/Unstable/Corrupted` — энергия якорей, `CA_MechXP` — механик-опыт.
* Ресурсы машины/игрока: `BP_ResourceManager_C._data.CurrentValues` (PlayerHealth, CarHealth,
  CarLim = батарея, Fuel, …). Копия для меню — `META/_data/Stats`.
* Инвентари: `BP_InventoryManager_C._data.Inventory_*`/`Inventories_Garage` → `ItemContainer`
  → `Slots` (`ItemSlot`/`ItemListSlot`/`ItemTileSlot`) → `Items` = массив ссылок на отдельные
  `ItemInstance` (1 объект = 1 предмет; `Archetype` = тип, `Properties.IP_Durability` и т.п.).
* Прочее: `BP_ProgressionManager_C` (забеги, экспедиции, `MaxRevealCharges`),
  `BP_MainCharacterManager_C.PlayerUpgradesUnlocked`, `BP_QuestManager_C` (миссии),
  `BP_StatusEffectManager_C` (причуды машины), `BP_StormManager_C`, `BP_TuningManager_C`.

`additems` клонирует последний предмет слота вместе с дочерними объектами (новые GUID и
уникальные `ItemInstance_N`). Предметы, содержащие собственный инвентарь, не клонируются.
Ёмкость tile-слотов (багажник) задаётся архетипом и в сейве не видна — не превышайте разумный стак.

## Проверено

* Все 15 бинарных сейвов из архива: декодирование → кодирование побайтно совпадает
  для OPTS/META/GAME; пересборка контейнера без изменений побайтно равна оригиналу.
* LZ4-компрессор редактора проверен эталонной библиотекой lz4 1.9.4.
* **Не проверено:** загрузка изменённого сейва самой игрой (запуска игры не было).
  Если игра не примет файл, она попробует резервные копии `odsaveN-backup-*.sav`
  («failed to load save slot %s, but there's available backups»).

## Что ещё выяснено (для визуального редактора)

* `Location` слота в сетке — центр предмета в полуклетках: `left = (X - w)/2`, `top = (Y - h)/2`;
  размер берётся из `ItemGridSizes[GridSize]` в DefaultGame.ini (поле TileWidth/Height устарело),
  зоны раскладки с `Attributes & 1` — заблокированные клетки. Проверено на 302 предметах.
* Стопка = `ItemStackSizes[NewStackSize]`. Свойства экземпляра (`Properties`) пишутся только при
  отличии от значения по умолчанию; максимумы — через тюнинг-теги `WB.Tuning.*` из `base.tune`.
* Эффекты (`SE_*`) — отдельные объекты с `_outer` = предмет и ссылкой в `ActiveEffects`.
* Исследования: `BP_InventionUnlockState.UnlockedNodes/PurchasedNodes` (купленные ⊂ доступные);
  улучшение гаража считается установленным, если на предмете-станции есть объект `UP_Garage_*`.
  Улучшения машины (`IU_*`) работают иначе (раскладка багажника, слоты креплений).
* В блоках Fig внутри ассетов FName тегов и TableId у FText пишутся индексом таблицы имён пакета.

## Заметки для дальнейшего анализа

* Консольные переменные сейвов в exe: `pd.save.binary`, `pd.save.compressed`,
  `pd.save.disablebackups`, `pd.save.allowthreading`, `pd.save.clearruntimecaches`,
  `pd.save.dump_item_orphans`, `pd.save.pause_on_load`, `pd.save.start_resume_game`,
  `pd.save.force_failDLC`, `pd.save.autosave_faketime`, `pd.save.async_faketime`.
  `pd.save.binary 0` должен заставить игру писать JSON (формат 1) — удобно для сверки.
* `Custom/Presets/*.json` (рядом с `Saved`) — официальные пользовательские пресеты сложности:
  блоки `settings` (поля `DrivingGameUserSettings`, напр. `HardcoreMode`, `EquippedCarPartsNoBreak`)
  и `tuning` (теги `WB.Tuning.*`). Для баланса это проще, чем правка сейва.
* `Custom/Radio/` — свои треки/плейлисты (mp3/wav/ogg/m3u, в т.ч. интернет-потоки) для радио.
* `Saved/<hash>/ga.sqlite3`, `ga_log*.txt` — очередь телеметрии GameAnalytics (плагин IWAnalytics).
* Плагины: Wwise, DLSS, Sentry (краш-репорты), HoudiniEngine, LogicDriverLite, IWPhotoMode,
  MinimapPlugin, SecondWindow; сжатие Oodle в движке. PDB в поставку не входит
  (упомянут лишь в `Manifest_DebugFiles_Win64.txt`).
* Строки форматов рядом с таблицей типов: `Int`, `GUID`, `DataBlock`, `ObjectBlock`,
  `SoftObject`, `SoftClass`, `LogDataBlock` — внутренние имена блоков сериализатора;
  код чтения/записи можно найти по xref на эти строки и на `-BIFSNX…` в Ghidra.
