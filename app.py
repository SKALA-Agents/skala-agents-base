from pathlib import Path

from dotenv import load_dotenv

from agents import InvestmentAnalysisService, ServiceConfig


NOTEBOOK_PATH = Path(__file__).resolve().parent / "notebooks" / "investment_report_service.ipynb"


def main() -> None:
    project_dir = Path(__file__).resolve().parent
    load_dotenv(project_dir / ".env")
    base_dir = InvestmentAnalysisService.resolve_base_dir(project_dir)
    service = InvestmentAnalysisService(base_dir=base_dir, config=ServiceConfig())
    result = service.run()
    print("Notebook path:")
    print(NOTEBOOK_PATH)
    print("Policy decision:")
    print(result.policy_decision)
    print("Report path:")
    print(result.output_path)


if __name__ == "__main__":
    main()
