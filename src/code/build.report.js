#!/usr/bin/env node
'use strict';

const fs = require('node:fs');
const path = require('node:path');
const readline = require('node:readline');

const repoRoot = path.resolve(__dirname, '..', '..');
const defaultFilmsDir = path.join(repoRoot, 'films');
const defaultOutputFile = path.join(repoRoot, 'films-report.md');
const filmNameCollator = new Intl.Collator('ru');

async function main() {
  try {
    const options = parseArgs(process.argv.slice(2));
    const sections = discoverSections(options.filmsDir);

    if (options.help) {
      printHelp(sections);
      return;
    }

    if (options.listSections) {
      printSections(sections);
      return;
    }

    const selectedSections = await resolveSelectedSections(sections, options);
    const report = buildReport(selectedSections);

    fs.writeFileSync(options.outputFile, report, 'utf8');
    console.log(`Report written to ${path.relative(repoRoot, options.outputFile)}`);
  } catch (error) {
    console.error(error.message);
    process.exitCode = 1;
  }
}

function parseArgs(args) {
  const options = {
    filmsDir: defaultFilmsDir,
    outputFile: defaultOutputFile,
    selectedSectionNames: [],
    listSections: false,
    interactive: null,
    help: false,
  };

  for (let index = 0; index < args.length; index += 1) {
    const arg = args[index];

    if (arg === '--help' || arg === '-h') {
      options.help = true;
      continue;
    }

    if (arg === '--list-sections') {
      options.listSections = true;
      continue;
    }

    if (arg === '--interactive' || arg === '-i') {
      options.interactive = true;
      continue;
    }

    if (arg === '--no-interactive') {
      options.interactive = false;
      continue;
    }

    if (arg === '--films-dir') {
      options.filmsDir = resolveCliPath(requireValue(args, ++index, arg));
      continue;
    }

    if (arg === '--output' || arg === '-o') {
      options.outputFile = resolveCliPath(requireValue(args, ++index, arg));
      continue;
    }

    if (arg === '--sections') {
      const names = requireValue(args, ++index, arg)
        .split(',')
        .map((name) => name.trim())
        .filter(Boolean);
      options.selectedSectionNames.push(...names);
      continue;
    }

    if (arg === '--section') {
      options.selectedSectionNames.push(requireValue(args, ++index, arg).trim());
      continue;
    }

    throw new Error(`Unknown argument: ${arg}`);
  }

  return options;
}

function requireValue(args, index, flagName) {
  const value = args[index];

  if (!value || value.startsWith('--')) {
    throw new Error(`Missing value for ${flagName}`);
  }

  return value;
}

function resolveCliPath(inputPath) {
  return path.isAbsolute(inputPath) ? inputPath : path.resolve(repoRoot, inputPath);
}

function discoverSections(filmsDir) {
  if (!fs.existsSync(filmsDir)) {
    throw new Error(`Films directory does not exist: ${filmsDir}`);
  }

  return fs
    .readdirSync(filmsDir, { withFileTypes: true })
    .filter((entry) => entry.isDirectory())
    .map((entry) => {
      const sectionPath = path.join(filmsDir, entry.name);
      const filmFiles = fs
        .readdirSync(sectionPath, { withFileTypes: true })
        .filter((child) => child.isFile() && /\.(ya?ml)$/i.test(child.name))
        .map((child) => path.join(sectionPath, child.name))
        .sort();

      return {
        name: entry.name,
        path: sectionPath,
        filmFiles,
      };
    })
    .filter((section) => section.filmFiles.length > 0)
    .sort((left, right) => filmNameCollator.compare(left.name, right.name));
}

function selectSections(sections, requestedNames) {
  if (requestedNames.length === 0) {
    return sections;
  }

  const requestedSet = new Set(requestedNames);
  const selectedSections = sections.filter((section) => requestedSet.has(section.name));
  const missingSections = requestedNames.filter(
    (name, index) => requestedNames.indexOf(name) === index && !selectedSections.some((section) => section.name === name),
  );

  if (missingSections.length > 0) {
    throw new Error(
      `Unknown sections: ${missingSections.join(', ')}\nAvailable sections: ${sections
        .map((section) => section.name)
        .join(', ')}`,
    );
  }

  return selectedSections;
}

async function resolveSelectedSections(sections, options) {
  const preselectedSections = selectSections(sections, options.selectedSectionNames);
  const shouldUseInteractiveSelector =
    options.interactive === true ||
    (options.interactive !== false &&
      options.selectedSectionNames.length === 0 &&
      process.stdin.isTTY &&
      process.stdout.isTTY);

  if (!shouldUseInteractiveSelector) {
    return preselectedSections;
  }

  if (!process.stdin.isTTY || !process.stdout.isTTY) {
    throw new Error('Interactive selection requires a terminal TTY. Use --sections or --no-interactive instead.');
  }

  const initiallySelectedNames =
    options.selectedSectionNames.length > 0
      ? preselectedSections.map((section) => section.name)
      : sections.map((section) => section.name);

  return promptForSections(sections, initiallySelectedNames);
}

function promptForSections(sections, initialSelectionNames) {
  if (sections.length === 0) {
    return Promise.resolve([]);
  }

  return new Promise((resolve, reject) => {
    const selectedNames = new Set(initialSelectionNames);
    const previousRawMode = process.stdin.isRaw === true;
    let cursorIndex = 0;
    let renderedLineCount = 0;
    let statusMessage = '';
    let finished = false;

    readline.emitKeypressEvents(process.stdin);

    if (typeof process.stdin.setRawMode === 'function') {
      process.stdin.setRawMode(true);
    }

    process.stdin.resume();
    render();
    process.stdin.on('keypress', onKeypress);

    function onKeypress(_, key = {}) {
      if (key.ctrl && key.name === 'c') {
        cleanup();
        reject(new Error('Selection cancelled.'));
        return;
      }

      if (key.name === 'up') {
        cursorIndex = (cursorIndex - 1 + sections.length) % sections.length;
        statusMessage = '';
        render();
        return;
      }

      if (key.name === 'down') {
        cursorIndex = (cursorIndex + 1) % sections.length;
        statusMessage = '';
        render();
        return;
      }

      if (key.name === 'space') {
        toggleSection(sections[cursorIndex].name);
        statusMessage = '';
        render();
        return;
      }

      if (key.name === 'return') {
        if (selectedNames.size === 0) {
          statusMessage = 'Select at least one section.';
          render();
          return;
        }

        const selectedSections = sections.filter((section) => selectedNames.has(section.name));
        cleanup();
        resolve(selectedSections);
        return;
      }

      if (key.name === 'escape' || key.name === 'q') {
        cleanup();
        reject(new Error('Selection cancelled.'));
        return;
      }

      if (key.name === 'a') {
        if (selectedNames.size === sections.length) {
          selectedNames.clear();
        } else {
          for (const section of sections) {
            selectedNames.add(section.name);
          }
        }

        statusMessage = '';
        render();
      }
    }

    function toggleSection(sectionName) {
      if (selectedNames.has(sectionName)) {
        selectedNames.delete(sectionName);
        return;
      }

      selectedNames.add(sectionName);
    }

    function render() {
      if (renderedLineCount > 0) {
        readline.moveCursor(process.stdout, 0, -renderedLineCount);
        readline.cursorTo(process.stdout, 0);
      }

      readline.clearScreenDown(process.stdout);

      const lines = [
        'Select sections for the report',
        'Use up/down arrows, space to toggle, a to toggle all, enter to confirm, q to cancel.',
        `Selected: ${selectedNames.size}/${sections.length}`,
        '',
      ];

      for (let index = 0; index < sections.length; index += 1) {
        const section = sections[index];
        const cursor = index === cursorIndex ? '>' : ' ';
        const mark = selectedNames.has(section.name) ? '[x]' : '[ ]';
        lines.push(`${cursor} ${mark} ${section.name} (${section.filmFiles.length})`);
      }

      if (statusMessage) {
        lines.push('');
        lines.push(statusMessage);
      }

      process.stdout.write(`${lines.join('\n')}\n`);
      renderedLineCount = lines.length;
    }

    function cleanup() {
      if (finished) {
        return;
      }

      finished = true;
      process.stdin.off('keypress', onKeypress);

      if (typeof process.stdin.setRawMode === 'function') {
        process.stdin.setRawMode(previousRawMode);
      }

      if (!previousRawMode) {
        process.stdin.pause();
      }

      if (renderedLineCount > 0) {
        readline.moveCursor(process.stdout, 0, -renderedLineCount);
        readline.cursorTo(process.stdout, 0);
        readline.clearScreenDown(process.stdout);
      }
    }
  });
}

function buildReport(sections) {
  const lines = [];
  const totalFilms = sections.reduce((sum, section) => sum + section.filmFiles.length, 0);

  lines.push('# Films Report');
  lines.push('');
  lines.push(`Sections: ${sections.map((section) => section.name).join(', ')}`);
  lines.push(`Total films: ${totalFilms}`);
  lines.push('');

  for (const section of sections) {
    lines.push(`## ${section.name}`);
    lines.push('');

    const films = section.filmFiles
      .map((filmFile) => parseFilmFile(filmFile))
      .sort((left, right) => filmNameCollator.compare(left.name, right.name));

    for (const film of films) {
      lines.push(`### ${film.name}`);
      lines.push(`Описание: ${film.description || '—'}`);
      lines.push(`Мнение: ${film.opinion || '—'}`);
      lines.push('');
    }
  }

  return `${lines.join('\n').trimEnd()}\n`;
}

function parseFilmFile(filePath) {
  const content = fs.readFileSync(filePath, 'utf8');
  const record = parseSimpleYamlRecord(content, filePath);

  return {
    name: record.name || path.basename(filePath, path.extname(filePath)),
    description: record.description || '',
    opinion: record.opinion || '',
  };
}

function parseSimpleYamlRecord(content, filePath) {
  const record = {};
  const lines = content.split(/\r?\n/);

  for (let index = 0; index < lines.length; index += 1) {
    const rawLine = lines[index];
    const trimmedLine = rawLine.trim();

    if (!trimmedLine || trimmedLine.startsWith('#')) {
      continue;
    }

    // The film catalog only uses single-line scalar fields, so a small parser is enough here.
    const match = rawLine.match(/^\s*([A-Za-z0-9_-]+):(?:\s*(.*))?$/);

    if (!match) {
      throw new Error(`Unsupported YAML syntax in ${filePath}:${index + 1}`);
    }

    const [, key, rawValue = ''] = match;
    record[key] = parseYamlScalar(rawValue.trim());
  }

  return record;
}

function parseYamlScalar(rawValue) {
  if (rawValue === '') {
    return '';
  }

  if (rawValue.startsWith('"') && rawValue.endsWith('"')) {
    try {
      return JSON.parse(rawValue);
    } catch (error) {
      return rawValue.slice(1, -1).replace(/\\"/g, '"');
    }
  }

  if (rawValue.startsWith("'") && rawValue.endsWith("'")) {
    return rawValue.slice(1, -1).replace(/''/g, "'");
  }

  return rawValue;
}

function printSections(sections) {
  if (sections.length === 0) {
    console.log('No sections with YAML films were found.');
    return;
  }

  console.log('Available sections:');
  for (const section of sections) {
    console.log(`- ${section.name} (${section.filmFiles.length})`);
  }
}

function printHelp(sections) {
  const availableSectionNames = sections.map((section) => section.name).join(', ');

  console.log(`Usage: node src/code/build.report.js [options]

Build a Markdown report from YAML files inside the films directory.

Options:
  --films-dir <path>      Override the films directory
  --output, -o <path>     Where to write the report (default: ${path.relative(repoRoot, defaultOutputFile)})
  --sections <a,b,c>      Include only the listed section folders
  --section <name>        Include one section folder, can be repeated
  --interactive, -i       Open terminal checkbox selector
  --no-interactive        Skip the terminal selector and use CLI arguments only
  --list-sections         Print available sections and exit
  --help, -h              Show this help

Available sections:
  ${availableSectionNames}`);
}

main();
