#为工程提供统一的绝对路径
import os

def get_project_root()->str:
    #当前文件的绝对路径
    current_file= os.path.abspath(__file__)
    #获取根目录
    root_path=os.path.dirname(current_file)
    #获取工程根目录
    project_root=os.path.dirname(root_path)
    return project_root

#根据相对路径获取绝对路径
def get_abs_path(relative_path:str)->str:
    project_root=get_project_root()
    abs_path=os.path.join(project_root,relative_path)
    return abs_path

if __name__=="__main__":
    print(get_project_root())
    print(get_abs_path("data\\维护保养.txt"))