import warnings
warnings.filterwarnings("ignore", category=DeprecationWarning)
import click
from pathlib import Path 
from vulcan.config.config import Configs
from vulcan.persistence.db_session import create_tables
from vulcan.orchestrator import main as run_vulcan


@click.group(help="VulCan - Autonomous Penetration Testing Agent")
def main():
    """Nhóm lệnh chính cho VulCan."""
    pass

@main.command("init", help="Initialize the project: create directories, database tables, and config files.")
def init():
    """Lệnh để khởi tạo môi trường cho VulCan."""
    # ✅ Thêm dòng này để xác định thư mục gốc dự án
    project_root = Path(__file__).resolve().parents[1]  # cli.py nằm trong vulcan/

    click.echo("--- Starting VulCan Initialization ---")
    
    # 1. Tạo các thư mục cần thiết
    try:
        Configs.basic_config.make_dirs()
        click.secho("✅ Created all data directories successfully.", fg="green")
    except Exception as e:
        click.secho(f"❌ Error creating directories: {e}", fg="red")
        return

    # 2. Tạo các bảng trong database
    try:
        create_tables()
        click.secho("✅ Initialized database tables successfully.", fg="green")
    except Exception as e:
        click.secho(f"❌ Error initializing database. Please check your db_config.yaml. Error: {e}", fg="red")
        return
        
    # 3. Tạo các tệp cấu hình mẫu (nếu chưa có)
    try:
        if not (project_root / "config.yaml").exists():
            Configs.create_all_templates()
            click.secho("✅ Generated default configuration files successfully.", fg="green")
        else:
            click.secho("ℹ️ Configuration files already exist, skipping generation.", fg="yellow")
    except Exception as e:
        click.secho(f"❌ Error generating config files: {e}", fg="red")
        return
        
    click.secho("--- VulCan Initialization Complete! ---", fg="green", bold=True)
    click.echo("You can now run 'vulcan start' to begin an assessment.")

# Thêm lệnh `start` vào nhóm lệnh `main`
main.add_command(run_vulcan, "start")

if __name__ == "__main__":
    main()
