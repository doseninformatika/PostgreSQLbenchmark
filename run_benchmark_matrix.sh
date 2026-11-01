#!/bin/bash
###############################################################################
# OLTP Benchmark Experiment Automation Script
#
# Menjalankan matriks eksperimen lengkap:
#   - 2 jenis workload: custom e-commerce vs baseline TPC-B
#   - 4 level concurrency: 10, 25, 50, 100
#   - 5 repetisi per kombinasi, dengan cold-cache reset di antaranya
#
# Total: 2 x 4 x 5 = 40 run
#
# PENTING: Jalankan script ini dengan sudo (untuk clear cache & restart service)
#   sudo bash run_benchmark_matrix.sh
###############################################################################

set -e

# ============ KONFIGURASI ============
DB_USER="postgres"
DB_HOST="localhost"
DB_CUSTOM="benchmark_db"           # database dengan skema e-commerce Anda
DB_BASELINE="benchmark_db_baseline" # database khusus baseline TPC-B

SCRIPT_DIR="/home/edison/oltp-benchmark"   # lokasi login.sql, browse.sql, purchase.sql
RESULTS_DIR="/home/edison/oltp-benchmark/results"

CONCURRENCY_LEVELS=(10 25 50 100)
THREADS=2
DURATION=60          # detik per run
REPETITIONS=5
COOLDOWN_SECONDS=5   # jeda setelah cold-cache reset, sebelum run berikutnya

# ============ SETUP AWAL ============
mkdir -p "$RESULTS_DIR"
cd "$SCRIPT_DIR"

echo "=================================================="
echo "OLTP Benchmark Experiment Matrix"
echo "Mulai: $(date)"
echo "=================================================="

# Cek apakah database baseline sudah ada, kalau belum, buat & init TPC-B
DB_EXISTS=$(sudo -u postgres psql -tAc "SELECT 1 FROM pg_database WHERE datname='$DB_BASELINE'")
if [ "$DB_EXISTS" != "1" ]; then
    echo ">> Database baseline belum ada. Membuat & inisialisasi TPC-B..."
    sudo -u postgres createdb "$DB_BASELINE"
    pgbench -i -s 1 -U "$DB_USER" -h "$DB_HOST" -d "$DB_BASELINE"
    echo ">> Baseline database siap."
else
    echo ">> Database baseline sudah ada, lanjut."
fi

# ============ FUNGSI: Cold-cache reset ============
cold_cache_reset() {
    echo "   -> Resetting cache (restart PostgreSQL + clear OS page cache)..."
    systemctl restart postgresql@16-main
    sleep 2
    sync && echo 3 > /proc/sys/vm/drop_caches
    sleep "$COOLDOWN_SECONDS"
}

# ============ FUNGSI: Jalankan satu run custom workload ============
run_custom() {
    local concurrency=$1
    local run_num=$2
    local outfile="$RESULTS_DIR/custom_c${concurrency}_run${run_num}.txt"

    echo ">> [CUSTOM] concurrency=$concurrency run=$run_num"
    pgbench -U "$DB_USER" -h "$DB_HOST" -d "$DB_CUSTOM" \
        -f "$SCRIPT_DIR/login.sql@60" \
        -f "$SCRIPT_DIR/browse.sql@25" \
        -f "$SCRIPT_DIR/purchase.sql@15" \
        -c "$concurrency" -j "$THREADS" -T "$DURATION" \
        > "$outfile" 2>&1

    echo "   -> Hasil disimpan: $outfile"
}

# ============ FUNGSI: Jalankan satu run baseline TPC-B ============
run_baseline() {
    local concurrency=$1
    local run_num=$2
    local outfile="$RESULTS_DIR/baseline_c${concurrency}_run${run_num}.txt"

    echo ">> [BASELINE] concurrency=$concurrency run=$run_num"
    pgbench -U "$DB_USER" -h "$DB_HOST" -d "$DB_BASELINE" \
        -c "$concurrency" -j "$THREADS" -T "$DURATION" \
        > "$outfile" 2>&1

    echo "   -> Hasil disimpan: $outfile"
}

# ============ MAIN LOOP ============
TOTAL_RUNS=$((${#CONCURRENCY_LEVELS[@]} * 2 * REPETITIONS))
CURRENT_RUN=0

for concurrency in "${CONCURRENCY_LEVELS[@]}"; do
    for run_num in $(seq 1 "$REPETITIONS"); do

        # --- Custom workload ---
        CURRENT_RUN=$((CURRENT_RUN + 1))
        echo ""
        echo "[$CURRENT_RUN/$TOTAL_RUNS] =================================="
        cold_cache_reset
        run_custom "$concurrency" "$run_num"

        # --- Baseline TPC-B ---
        CURRENT_RUN=$((CURRENT_RUN + 1))
        echo ""
        echo "[$CURRENT_RUN/$TOTAL_RUNS] =================================="
        cold_cache_reset
        run_baseline "$concurrency" "$run_num"

    done
done

echo ""
echo "=================================================="
echo "Selesai: $(date)"
echo "Semua hasil tersimpan di: $RESULTS_DIR"
echo "Total file hasil: $(ls "$RESULTS_DIR" | wc -l)"
echo "=================================================="
