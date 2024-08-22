import os

path = '/Users/Sarthak/Desktop/Project/KE copy'

for folder in os.listdir(path):
    if "#" in folder:
        new_folder = folder.replace("#", "")
        os.rename(os.path.join(path, folder), os.path.join(path, new_folder))

for folder in os.listdir(path):
    if "#" in folder:
        print("oops")
        break
    print("done")
