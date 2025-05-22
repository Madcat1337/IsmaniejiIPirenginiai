import json

# Read users1.json
with open('users1.json', 'r') as file1:
    users1 = json.load(file1)

# Read users2.json
with open('users2.json', 'r') as file2:
    users2 = json.load(file2)

# Merge data from user2 into user1 
users1["table"]["users"].update(users2["table"]["users"])

# Save the merged data to a new JSON file
with open('merged_users.json', 'w') as outfile:
    json.dump(users1, outfile, indent=4)

print("Users merged successfully into merged_users.json") 