#!/usr/bin/env python3
"""Extract all PDFs from org-materials/ subdirectories to text files.

Scans grant-applications/, progress-reports/, work-plans/ directories and
the org-materials/ root for PDF files. Extracts text using pdfplumber with
layout=True and writes to org-materials/.extracted-text/.

Skips extraction if the output .txt file already exists (idempotent).
Validates extracted text is non-empty and logs warnings for empty/short output.
"""

import os
import sys
import argparse

import pdfplumber


# Directories to scan for PDFs (relative to org-materials/)
SUBDIRS = ["grant-applications", "progress-reports", "work-plans"]

# Minimum expected text length for a multi-page PDF
MIN_TEXT_LENGTH = 100


def find_pdfs(org_materials_dir: str) -> list[tuple[str, str]]:
    """Find all PDF files in org-materials/ and subdirectories.

    Returns list of (pdf_path, subdir_name) tuples.
    subdir_name is "" for root-level PDFs.
    """
    pdfs = []

    # Scan subdirectories
    for subdir in SUBDIRS:
        subdir_path = os.path.join(org_materials_dir, subdir)
        if not os.path.isdir(subdir_path):
            print(f"  WARNING: Directory not found: {subdir_path}")
            continue
        for filename in sorted(os.listdir(subdir_path)):
            if filename.lower().endswith(".pdf"):
                pdfs.append((os.path.join(subdir_path, filename), subdir))

    # Scan root directory for standalone PDFs
    for filename in sorted(os.listdir(org_materials_dir)):
        filepath = os.path.join(org_materials_dir, filename)
        if os.path.isfile(filepath) and filename.lower().endswith(".pdf"):
            pdfs.append((filepath, ""))

    return pdfs


def pdf_to_output_name(pdf_path: str) -> str:
    """Generate output filename: replace spaces with underscores, .pdf -> .txt."""
    basename = os.path.basename(pdf_path)
    name = basename.replace(" ", "_")
    if name.lower().endswith(".pdf"):
        name = name[:-4] + ".txt"
    return name


def extract_pdf(pdf_path: str) -> str:
    """Extract text from a PDF using pdfplumber with layout=True."""
    pages_text = []
    with pdfplumber.open(pdf_path) as pdf:
        for page in pdf.pages:
            text = page.extract_text(layout=True)
            if text:
                pages_text.append(text)
    return "\n\n".join(pages_text)


def main():
    parser = argparse.ArgumentParser(description="Extract PDFs from org-materials/ to text")
    parser.add_argument(
        "--org-materials",
        default=os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "org-materials"),
        help="Path to org-materials/ directory (default: ../org-materials relative to script)",
    )
    args = parser.parse_args()

    org_dir = args.org_materials
    output_dir = os.path.join(org_dir, ".extracted-text")

    if not os.path.isdir(org_dir):
        print(f"ERROR: org-materials directory not found: {org_dir}")
        sys.exit(1)

    os.makedirs(output_dir, exist_ok=True)

    print(f"Scanning for PDFs in: {org_dir}")
    print(f"Output directory: {output_dir}")
    print()

    pdfs = find_pdfs(org_dir)
    print(f"Found {len(pdfs)} PDF files\n")

    stats = {"total": len(pdfs), "skipped": 0, "extracted": 0, "failed": 0}

    for pdf_path, subdir in pdfs:
        basename = os.path.basename(pdf_path)
        output_name = pdf_to_output_name(pdf_path)
        output_path = os.path.join(output_dir, output_name)

        source_label = f"{subdir}/{basename}" if subdir else basename

        # Skip if already extracted (idempotent per D-07)
        if os.path.exists(output_path):
            print(f"  SKIP (exists): {source_label} -> {output_name}")
            stats["skipped"] += 1
            continue

        print(f"  Extracting: {source_label} -> {output_name} ... ", end="", flush=True)

        try:
            text = extract_pdf(pdf_path)

            # Validation: check extracted text quality
            if not text or len(text) == 0:
                print("WARNING (empty output - may be scanned image)")
                stats["failed"] += 1
                # Write empty file so we don't retry scanned PDFs
                with open(output_path, "w", encoding="utf-8") as f:
                    f.write("")
                continue

            if len(text) < MIN_TEXT_LENGTH:
                print(f"WARNING (short output: {len(text)} chars)")
            else:
                print(f"OK ({len(text)} chars)")

            with open(output_path, "w", encoding="utf-8") as f:
                f.write(text)

            stats["extracted"] += 1

        except Exception as e:
            print(f"ERROR: {e}")
            stats["failed"] += 1

    # Summary
    print()
    print("=" * 50)
    print("Extraction Summary")
    print("=" * 50)
    print(f"  Total PDFs found:      {stats['total']}")
    print(f"  Already extracted:     {stats['skipped']}")
    print(f"  Newly extracted:       {stats['extracted']}")
    print(f"  Failed/empty:          {stats['failed']}")
    print("=" * 50)


if __name__ == "__main__":
    main()
