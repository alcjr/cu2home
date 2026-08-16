import csv
from pathlib import Path

from django.conf import settings
from django.contrib.gis.geos import Point
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from apps.properties.models import Municipality


class Command(BaseCommand):
    help = 'Update municipality coordinates from CSV file'

    def add_arguments(self, parser):
        parser.add_argument(
            '--file',
            type=str,
            default='municipios_coordenadas.csv',
            help='Path to CSV file with coordinates',
        )
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Show what would be updated without saving',
        )

    def handle(self, *args, **options):
        csv_file = self._resolve_path(options['file'])
        dry_run = options['dry_run']

        # ✅ CORREGIDO: NOTICE en mayúsculas
        self.stdout.write(self.style.NOTICE(
            f'{"[DRY RUN] " if dry_run else ""}Reading from: {csv_file}'
        ))

        try:
            with open(csv_file, 'r', encoding='utf-8-sig') as f:
                reader = csv.DictReader(f)
                self._validate_columns(reader.fieldnames)
                rows = list(reader)
        except FileNotFoundError:
            raise CommandError(f'File not found: {csv_file}')
        except csv.Error as e:
            raise CommandError(f'Error parsing CSV: {e}')

        stats = {'updated': 0, 'not_found': 0, 'invalid': 0, 'errors': 0}

        existing_ids = set(Municipality.objects.values_list('id', flat=True))
        municipalities_to_update = []

        for idx, row in enumerate(rows, start=2):
            try:
                result = self._process_row(
                    row, existing_ids, dry_run, municipalities_to_update
                )
                
                if result == 'updated':
                    stats['updated'] += 1
                elif result == 'not_found':
                    stats['not_found'] += 1
                    self.stdout.write(self.style.WARNING(
                        f'✗ Row {idx}: ID {row.get("id", "?")} not found'
                    ))
                elif result == 'invalid':
                    stats['invalid'] += 1
                    self.stdout.write(self.style.WARNING(
                        f'✗ Row {idx}: Invalid coordinates'
                    ))
                    
            except (ValueError, KeyError) as e:
                stats['errors'] += 1
                self.stdout.write(self.style.ERROR(
                    f'✗ Row {idx}: {e}'
                ))

        if municipalities_to_update and not dry_run:
            with transaction.atomic():
                Municipality.objects.bulk_update(
                    municipalities_to_update,
                    ['latitude', 'longitude', 'location'],
                    batch_size=1000,
                )

        self._print_summary(stats, dry_run)

    def _resolve_path(self, csv_file: str) -> Path:
        path = Path(csv_file)
        
        if path.is_absolute():
            return path.resolve()

        candidates = [
            Path(settings.BASE_DIR) / path,
            Path(settings.BASE_DIR) / 'data' / path,
            path,
        ]
        
        for candidate in candidates:
            if candidate.exists():
                return candidate.resolve()
                
        raise CommandError(
            f'File not found. Searched in: '
            f'{", ".join(str(c) for c in candidates)}'
        )

    def _validate_columns(self, fieldnames):
        required = {'id', 'latitude', 'longitude'}
        missing = required - set(fieldnames or [])
        if missing:
            raise CommandError(f'Missing columns in CSV: {", ".join(missing)}')

    def _process_row(self, row: dict, existing_ids: set, dry_run: bool, to_update: list):
        municipality_id = int(row['id'].strip())
        latitude = float(row['latitude'].strip())
        longitude = float(row['longitude'].strip())

        if not (-90 <= latitude <= 90) or not (-180 <= longitude <= 180):
            return 'invalid'

        if municipality_id not in existing_ids:
            return 'not_found'

        if dry_run:
            self.stdout.write(
                f'[DRY RUN] Would update ID {municipality_id} '
                f'-> ({latitude}, {longitude})'
            )
            return 'updated'

        municipality = Municipality(
            id=municipality_id,
            latitude=latitude,
            longitude=longitude,
            location=Point(longitude, latitude, srid=4326),
        )
        to_update.append(municipality)
        self.stdout.write(
            self.style.SUCCESS(f'✓ ID {municipality_id} -> ({latitude}, {longitude})')
        )
        return 'updated'

    def _print_summary(self, stats: dict, dry_run: bool):
        prefix = '[DRY RUN] ' if dry_run else ''
        self.stdout.write('\n' + '=' * 50)
        self.stdout.write(self.style.SUCCESS(
            f'{prefix}✅ Updated: {stats["updated"]}'
        ))
        if stats['not_found']:
            self.stdout.write(self.style.WARNING(
                f'⚠️  Not found: {stats["not_found"]}'
            ))
        if stats['invalid']:
            self.stdout.write(self.style.WARNING(
                f'⚠️  Invalid coords: {stats["invalid"]}'
            ))
        if stats['errors']:
            self.stdout.write(self.style.ERROR(
                f'❌ Parse errors: {stats["errors"]}'
            ))
        self.stdout.write(f'📊 Total rows: {sum(stats.values())}')
        self.stdout.write('=' * 50)
