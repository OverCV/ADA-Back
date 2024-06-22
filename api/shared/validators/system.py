from sqlalchemy.orm import Session

from data.tables import SystemTable
from utils.funcs import printnl


def exist_system_id(system_id: int, db: Session) -> bool:
    db_system: SystemTable = db.query(SystemTable).filter(
        SystemTable.id == system_id
    ).first()
    return False if db_system is None else True


def exist_system_title(system_title: str, db: Session) -> bool:
    db_system: SystemTable = db.query(SystemTable).filter(
        SystemTable.title == system_title
    ).first()
    return not(db_system is None)
