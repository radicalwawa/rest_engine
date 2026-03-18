import json
matrix = json.load(open('/dev/stdin'))
with open('domain/suno_identity_matrix.json', 'w') as f:
    json.dump(matrix, f, indent=2, ensure_ascii=False)
print('saved to domain/suno_identity_matrix.json')
