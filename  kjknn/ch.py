def remove_duplicates_preserve_order(input_file, output_file):
    seen = set()
    with open(input_file, 'r', encoding='utf-8') as infile, \
         open(output_file, 'w', encoding='utf-8') as outfile:
        for line in infile:
            if line not in seen:
                outfile.write(line)
                seen.add(line)

# Usage
remove_duplicates_preserve_order(' kjknn/input.txt', ' kjknn/output.txt')