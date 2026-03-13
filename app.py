import argparse
from pathlib import Path

def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run the investment analysis pipeline for a list of companies."
    )
    parser.add_argument(
        "companies",
        nargs="+",
        help="Company names to research and evaluate in sequence.",
    )
    parser.add_argument(
        "--domain",
        default="AI Semiconductor",
        help="Domain to analyze. Defaults to AI Semiconductor.",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    from agents import InvestmentAnalysisService, ServiceConfig

    base_dir = InvestmentAnalysisService.resolve_base_dir(Path(__file__).resolve().parent)
    service = InvestmentAnalysisService(
        base_dir=base_dir,
        config=ServiceConfig(companies=args.companies, domain=args.domain),
    )
    result = service.run()
    print("Input companies:")
    print(", ".join(result.input_companies))
    print("Policy decision:")
    print(result.policy_decision)
    print("Report path:")
    print(result.output_path)


if __name__ == "__main__":
    main()
