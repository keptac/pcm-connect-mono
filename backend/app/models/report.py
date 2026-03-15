from datetime import datetime, date
from sqlalchemy import Column, Integer, String, DateTime, ForeignKey, Date
from sqlalchemy.orm import relationship
from ..db.base import Base


class ReportTemplate(Base):
    __tablename__ = "report_templates"

    id = Column(Integer, primary_key=True)
    name = Column(String, nullable=False)
    version = Column(String, nullable=False)
    columns_json = Column(String, nullable=False)
    file_format = Column(String, default="csv")
    created_by = Column(Integer, ForeignKey("users.id"), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)


class UploadedReport(Base):
    __tablename__ = "uploaded_reports"

    id = Column(Integer, primary_key=True)
    template_id = Column(Integer, ForeignKey("report_templates.id"), nullable=True)
    university_id = Column(Integer, ForeignKey("universities.id"), nullable=True)
    period_start = Column(Date, nullable=False)
    period_end = Column(Date, nullable=False)
    report_type = Column(String, nullable=True)
    original_filename = Column(String, nullable=False)
    stored_path = Column(String, nullable=False)
    status = Column(String, default="uploaded")
    uploaded_by = Column(Integer, ForeignKey("users.id"), nullable=True)
    uploaded_at = Column(DateTime, default=datetime.utcnow)
    processed_at = Column(DateTime, nullable=True)
    error_summary = Column(String, nullable=True)

    rows = relationship("ParsedReportRow", back_populates="report", cascade="all, delete-orphan")


class ParsedReportRow(Base):
    __tablename__ = "parsed_report_rows"

    id = Column(Integer, primary_key=True)
    uploaded_report_id = Column(Integer, ForeignKey("uploaded_reports.id"), nullable=False)
    row_index = Column(Integer, nullable=False)
    data_json = Column(String, nullable=False)
    is_valid = Column(String, default="true")
    validation_errors_json = Column(String, nullable=True)

    report = relationship("UploadedReport", back_populates="rows")
