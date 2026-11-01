"""
Parse hasil eksperimen pgbench (40 file .txt) menjadi CSV terstruktur.

Menghasilkan 2 file output:
  1. raw_results.csv        - data mentah per run (termasuk breakdown per skrip untuk custom)
  2. aggregated_results.csv - hasil agregasi (mean, stddev) per kombinasi skenario

Jalankan dari dalam folder yang berisi folder 'results':
  python3 parse_results.py
"""

import re
import csv
import glob
import os
import statistics

RESULTS_DIR = "results"
RAW_OUTPUT = "raw_results.csv"
AGG_OUTPUT = "aggregated_results.csv"


def parse_file(filepath):
    """Parse satu file hasil pgbench. Return list of dict (1 baris per skrip)."""
    with open(filepath, "r", errors="ignore") as f:
        content = f.read()

    filename = os.path.basename(filepath)
    # contoh nama file: custom_c10_run1.txt / baseline_c50_run3.txt
    m = re.match(r"(custom|baseline)_c(\d+)_run(\d+)\.txt", filename)
    if not m:
        print(f"  [!] Nama file tidak sesuai pola, dilewati: {filename}")
        return []

    workload_type, concurrency, run_num = m.group(1), int(m.group(2)), int(m.group(3))

    rows = []

    if workload_type == "custom":
        # --- Baris ringkasan keseluruhan (gabungan ketiga skrip) ---
        # Contoh baris di output pgbench:
        #   number of transactions actually processed: 26431
        #   number of failed transactions: 0 (0.000%)
        #   latency average = 22.602 ms
        #   tps = 442.441945 (without initial connection time)
        overall_tx = re.search(r"number of transactions actually processed: (\d+)", content)
        overall_failed = re.search(r"number of failed transactions: (\d+)", content)
        overall_lat = re.search(r"^latency average = ([\d.]+) ms", content, re.MULTILINE)
        overall_tps = re.search(r"^tps = ([\d.]+)", content, re.MULTILINE)

        if overall_tx and overall_lat and overall_tps:
            rows.append({
                "workload_type": workload_type,
                "concurrency": concurrency,
                "run": run_num,
                "script": "custom_overall",
                "transactions": int(overall_tx.group(1)),
                "failed_transactions": int(overall_failed.group(1)) if overall_failed else None,
                "tps": float(overall_tps.group(1)),
                "latency_avg_ms": float(overall_lat.group(1)),
                "latency_stddev_ms": None,  # tidak ada stddev gabungan di output pgbench
                "source_file": filename,
            })
        else:
            print(f"  [!] Gagal parsing baris ringkasan keseluruhan di: {filename}")

        # --- Cari blok per-skrip: "SQL script N: nama.sql" ... tps = X ... latency average = Y ms ---
        script_blocks = re.findall(
            r"SQL script \d+: (\S+)\s*"
            r"- weight: \d+.*?"
            r"- (\d+) transactions.*?tps = ([\d.]+)\)\s*"
            r"- number of failed transactions: (\d+).*?"
            r"- latency average = ([\d.]+) ms\s*"
            r"- latency stddev = ([\d.]+) ms",
            content, re.DOTALL
        )
        if not script_blocks:
            print(f"  [!] Gagal parsing blok skrip di: {filename}")
        for script_path, n_tx, tps, failed, lat_avg, lat_stddev in script_blocks:
            script_name = os.path.basename(script_path)  # buang path, sisakan nama file saja
            rows.append({
                "workload_type": workload_type,
                "concurrency": concurrency,
                "run": run_num,
                "script": script_name,
                "transactions": int(n_tx),
                "failed_transactions": int(failed),
                "tps": float(tps),
                "latency_avg_ms": float(lat_avg),
                "latency_stddev_ms": float(lat_stddev),
                "source_file": filename,
            })

    else:  # baseline
        tps_match = re.search(r"tps = ([\d.]+)", content)
        lat_match = re.search(r"latency average = ([\d.]+) ms", content)
        tx_match = re.search(r"number of transactions actually processed: (\d+)", content)
        failed_match = re.search(r"number of failed transactions: (\d+)", content)

        if tps_match and lat_match:
            rows.append({
                "workload_type": workload_type,
                "concurrency": concurrency,
                "run": run_num,
                "script": "tpcb_overall",
                "transactions": int(tx_match.group(1)) if tx_match else None,
                "failed_transactions": int(failed_match.group(1)) if failed_match else None,
                "tps": float(tps_match.group(1)),
                "latency_avg_ms": float(lat_match.group(1)),
                "latency_stddev_ms": None,  # baseline overall tidak selalu ada stddev
                "source_file": filename,
            })
        else:
            print(f"  [!] Gagal parsing (mungkin run gagal/kosong): {filename}")

    return rows


def main():
    files = sorted(glob.glob(os.path.join(RESULTS_DIR, "*.txt")))
    print(f"Ditemukan {len(files)} file hasil di folder '{RESULTS_DIR}'.\n")

    all_rows = []
    for fp in files:
        all_rows.extend(parse_file(fp))

    if not all_rows:
        print("Tidak ada data berhasil di-parse. Cek format file hasil.")
        return

    # ---- Simpan raw results ----
    fieldnames = [
        "workload_type", "concurrency", "run", "script",
        "transactions", "failed_transactions",
        "tps", "latency_avg_ms", "latency_stddev_ms", "source_file",
    ]
    with open(RAW_OUTPUT, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(all_rows)
    print(f"Raw results disimpan ke: {RAW_OUTPUT} ({len(all_rows)} baris)")

    # ---- Agregasi: mean & stddev per (workload_type, concurrency, script) ----
    groups = {}
    for row in all_rows:
        key = (row["workload_type"], row["concurrency"], row["script"])
        groups.setdefault(key, {"tps": [], "latency_avg_ms": []})
        groups[key]["tps"].append(row["tps"])
        groups[key]["latency_avg_ms"].append(row["latency_avg_ms"])

    agg_rows = []
    for (workload_type, concurrency, script), vals in sorted(groups.items()):
        n = len(vals["tps"])
        tps_mean = statistics.mean(vals["tps"])
        tps_std = statistics.stdev(vals["tps"]) if n > 1 else 0.0
        lat_mean = statistics.mean(vals["latency_avg_ms"])
        lat_std = statistics.stdev(vals["latency_avg_ms"]) if n > 1 else 0.0

        agg_rows.append({
            "workload_type": workload_type,
            "concurrency": concurrency,
            "script": script,
            "n_runs": n,
            "tps_mean": round(tps_mean, 3),
            "tps_stddev": round(tps_std, 3),
            "latency_avg_mean_ms": round(lat_mean, 3),
            "latency_avg_stddev_ms": round(lat_std, 3),
        })

    with open(AGG_OUTPUT, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=[
            "workload_type", "concurrency", "script", "n_runs",
            "tps_mean", "tps_stddev", "latency_avg_mean_ms", "latency_avg_stddev_ms",
        ])
        writer.writeheader()
        writer.writerows(agg_rows)
    print(f"Aggregated results disimpan ke: {AGG_OUTPUT} ({len(agg_rows)} baris)")

    print("\nSelesai. Buka kedua file CSV ini untuk analisis lebih lanjut (Excel/pandas).")


if __name__ == "__main__":
    main()
