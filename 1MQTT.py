import json

x = '{"firstName": "Lukas", "lastName": "Pivoras", "age": "25", "city": "Moletai"}'

y = json.loads(x)

print(y);