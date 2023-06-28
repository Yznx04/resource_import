import git
import gitlab
from apscheduler.schedulers.blocking import BlockingScheduler


def sync_github_to_local(github_repo_url, local_repo_path):
    repo = git.Repo.clone_from(github_repo_url, local_repo_path, branch='master')
    for branch in repo.remote().refs:
        if branch.name != 'origin/master':
            repo.git.checkout(branch.name)


def sync_local_to_gitlab(local_repo_path, gitlab_project_id, gitlab_access_token):
    gl = gitlab.Gitlab('https://gitlab.com', private_token=gitlab_access_token)
    project = gl.projects.get(gitlab_project_id)
    for file in project.repository_tree():
        if file['type'] == 'tree':
            continue
        with open(local_repo_path + '/' + file['name'], 'r') as f:
            content = f.read()
            project.files.create({
                'file_path': file['name'],
                'branch': 'master',
                'content': content,
                'commit_message': 'Sync from GitHub'
            })


def schedule_sync():
    github_repo_url = 'https://github.com/your_github_usernameyour_github_repo.git'
    local_repo_path = '/path/to/local/repo'
    gitlab_project_id = 'your_gitlab_project_id'
    gitlab_access_token = 'your_gitlab_access_token'

    sync_github_to_local(github_repo_url, local_repo_path)
    sync_local_to_gitlab(local_repo_path, gitlab_project_id, gitlab_access_token)


scheduler = BlockingScheduler()
scheduler.add_job(schedule_sync, 'interval', minutes=30)  # 每30分钟同步一次
scheduler.start()
