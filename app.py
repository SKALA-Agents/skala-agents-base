import argparse
from pathlib import Path

from dotenv import load_dotenv

from agents import InvestmentAnalysisService, ServiceConfig


NOTEBOOK_PATH = Path(__file__).resolve().parent / "notebooks" / "investment_report_service.ipynb"
DEFAULT_QUERY = "AI 반도체 스타트업을 투자하고 싶은데 투자 가치가 있는 기업을 찾아줘"


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("query", nargs="?", default=DEFAULT_QUERY)
    args = parser.parse_args()

    project_dir = Path(__file__).resolve().parent
    load_dotenv(project_dir / ".env")
    base_dir = InvestmentAnalysisService.resolve_base_dir(project_dir)
    service = InvestmentAnalysisService(base_dir=base_dir, config=ServiceConfig())
    result = service.run(query=args.query)
    print("User query:")
    print(args.query)
    print("Resolved domain:")
    print(result.domain)
    print("Notebook path:")
    print(NOTEBOOK_PATH)
    print("Policy decision:")
    print(result.policy_decision)
    print("Report path:")
    print(result.output_path)


if __name__ == "__main__":
    main()
