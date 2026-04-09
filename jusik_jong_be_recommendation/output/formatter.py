"""
Rich 기반 콘솔 출력 포맷터
"""
from typing import Optional
from datetime import datetime
import pytz
from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich.text import Text
from rich import box

KST = pytz.timezone("Asia/Seoul")
console = Console()


def print_header(market_data: Optional[dict], futures_data: Optional[dict]) -> None:
    """시황 헤더 출력"""
    now = datetime.now(KST).strftime("%Y-%m-%d %H:%M:%S KST")

    kospi_chg  = (market_data or {}).get("kospi", {}).get("change_pct", 0)
    kosdaq_chg = (market_data or {}).get("kosdaq", {}).get("change_pct", 0)
    kospi_val  = (market_data or {}).get("kospi", {}).get("current", 0)
    kosdaq_val = (market_data or {}).get("kosdaq", {}).get("current", 0)
    bias       = (market_data or {}).get("market_bias", "neutral")

    sp500_pct  = (futures_data or {}).get("sp500_pct", 0)
    nasdaq_pct = (futures_data or {}).get("nasdaq_pct", 0)
    vix        = (futures_data or {}).get("vix", 0)
    us_sent    = (futures_data or {}).get("sentiment", "neutral")

    # 색상
    kospi_color  = "green" if kospi_chg  >= 0 else "red"
    kosdaq_color = "green" if kosdaq_chg >= 0 else "red"
    sp500_color  = "green" if sp500_pct  >= 0 else "red"
    nas_color    = "green" if nasdaq_pct >= 0 else "red"

    bias_icons = {
        "bullish": "[bold green]BULLISH[/]",
        "neutral": "[bold yellow]NEUTRAL[/]",
        "bearish": "[bold red]BEARISH[/]",
        "crash":   "[bold red]CRASH[/]",
    }

    us_sent_display = {
        "risk_on":      "[green]RISK ON[/]",
        "neutral":      "[yellow]NEUTRAL[/]",
        "risk_off":     "[red]RISK OFF[/]",
        "fear":         "[red]FEAR[/]",
        "extreme_fear": "[bold red]EXTREME FEAR[/]",
    }.get(us_sent, us_sent)

    content = (
        f"[bold]시간:[/] {now}\n"
        f"[bold]KOSPI:[/] [{kospi_color}]{kospi_val:,.2f} ({kospi_chg:+.2f}%)[/]  "
        f"[bold]KOSDAQ:[/] [{kosdaq_color}]{kosdaq_val:,.2f} ({kosdaq_chg:+.2f}%)[/]  "
        f"시황: {bias_icons.get(bias, bias)}\n"
        f"[bold]미국선물:[/] S&P [{sp500_color}]{sp500_pct:+.2f}%[/]  "
        f"NASDAQ [{nas_color}]{nasdaq_pct:+.2f}%[/]  "
        f"VIX [yellow]{vix:.1f}[/]  {us_sent_display}"
    )

    console.print(Panel(
        content,
        title="[bold blue]종가 베팅 추천 시스템[/bold blue]",
        border_style="blue",
        expand=True,
    ))


def print_recommendations(recs: list[dict]) -> None:
    """추천 종목 테이블 출력"""
    if not recs:
        console.print(
            Panel(
                "[bold red]추천 종목 없음[/bold red]\n"
                "시장 상황이 종가 베팅에 적합하지 않습니다.",
                border_style="red",
            )
        )
        return

    table = Table(
        title="[bold]종가 베팅 추천 종목[/bold]",
        box=box.DOUBLE_EDGE,
        show_lines=True,
        header_style="bold magenta",
    )

    table.add_column("순위", justify="center", width=4)
    table.add_column("코드",  justify="center", width=8)
    table.add_column("종목명", justify="left",   width=14)
    table.add_column("점수",  justify="center", width=7)
    table.add_column("테마",  justify="left",   width=12)
    table.add_column("현재가", justify="right",  width=10)
    table.add_column("목표가", justify="right",  width=10)
    table.add_column("손절가", justify="right",  width=10)
    table.add_column("손익비", justify="center", width=7)

    for i, rec in enumerate(recs, 1):
        score      = rec.get("score", 0)
        close      = rec.get("close", 0)
        target     = rec.get("target_price", 0)
        stop       = rec.get("stop_price", 0)
        rr         = rec.get("rr_ratio", 0)

        target_pct = (target - close) / close * 100 if close > 0 else 0
        stop_pct   = (stop - close)   / close * 100 if close > 0 else 0

        score_color = (
            "bold green" if score >= 0.75
            else "green" if score >= 0.60
            else "yellow" if score >= 0.50
            else "red"
        )

        table.add_row(
            str(i),
            rec.get("ticker", ""),
            rec.get("name", "")[:12],
            f"[{score_color}]{score:.3f}[/]",
            rec.get("theme", "")[:10],
            f"{close:,}",
            f"[green]{target:,}[/] [dim]({target_pct:+.1f}%)[/]",
            f"[red]{stop:,}[/] [dim]({stop_pct:+.1f}%)[/]",
            f"1:{rr:.1f}",
        )

    console.print(table)
    console.print()


def print_reasons(recs: list[dict]) -> None:
    """추천 근거 상세 출력"""
    if not recs:
        return

    console.print("[bold]추천 근거 상세[/bold]")
    for i, rec in enumerate(recs, 1):
        ticker = rec.get("ticker", "")
        name   = rec.get("name", "")
        reason = rec.get("reason", "")
        scores = rec.get("scores", {})

        score_str = " | ".join(
            f"{k[:4]}: {v:.2f}"
            for k, v in scores.items()
            if v is not None
        )

        console.print(
            f"  [bold cyan]{i}. {name}[/bold cyan] ({ticker})\n"
            f"     [dim]근거:[/dim] {reason}\n"
            f"     [dim]세부점수:[/dim] {score_str}"
        )
    console.print()


def print_warning(message: str) -> None:
    console.print(f"[bold yellow]경고:[/bold yellow] {message}")


def print_error(message: str) -> None:
    console.print(f"[bold red]오류:[/bold red] {message}")


def print_info(message: str) -> None:
    console.print(f"[dim]{message}[/dim]")
