#!/usr/bin/env python3
"""
Auto Download Estratégia Concursos
Baixador automático de cursos com anti-detecção, retry automático e downloads paralelos.
"""

import os
import re
import time
import argparse
import sys
import json
from urllib.parse import urljoin
from functools import wraps
from concurrent.futures import ThreadPoolExecutor, as_completed
import threading
from queue import Queue

import requests
from seleniumbase import SB
from tqdm import tqdm
from colorama import init, Fore, Style

# Inicializa colorama para Windows
init(autoreset=True)

# --- Configurações ---
BASE_URL = "https://www.estrategiaconcursos.com.br"
MY_COURSES_URL = urljoin(BASE_URL, "/app/dashboard/cursos")
MAX_RETRIES = 3
RETRY_DELAY = 2  # segundos
MAX_PARALLEL_DOWNLOADS = 3  # downloads simultâneos


# --- Helpers de Log Colorido ---
def log_info(msg):
    print(f"{Fore.CYAN}ℹ {msg}{Style.RESET_ALL}")

def log_success(msg):
    print(f"{Fore.GREEN}✓ {msg}{Style.RESET_ALL}")

def log_warning(msg):
    print(f"{Fore.YELLOW}⚠ {msg}{Style.RESET_ALL}")

def log_error(msg):
    print(f"{Fore.RED}✗ {msg}{Style.RESET_ALL}")

def log_header(msg):
    print(f"\n{Fore.MAGENTA}{'='*60}{Style.RESET_ALL}")
    print(f"{Fore.MAGENTA}{msg}{Style.RESET_ALL}")
    print(f"{Fore.MAGENTA}{'='*60}{Style.RESET_ALL}")


# --- Decorator de Retry ---
def retry_on_failure(max_retries=MAX_RETRIES, delay=RETRY_DELAY):
    """Decorator para retry com backoff exponencial."""
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            last_exception = None
            for attempt in range(max_retries):
                try:
                    return func(*args, **kwargs)
                except Exception as e:
                    last_exception = e
                    wait_time = delay * (2 ** attempt)
                    log_warning(f"Tentativa {attempt + 1}/{max_retries} falhou: {e}")
                    if attempt < max_retries - 1:
                        log_info(f"Aguardando {wait_time}s antes de tentar novamente...")
                        time.sleep(wait_time)
            log_error(f"Todas as {max_retries} tentativas falharam.")
            raise last_exception
        return wrapper
    return decorator


# --- Funções Auxiliares ---
def sanitize_filename(original_filename):
    """Remove caracteres inválidos de um nome de arquivo."""
    sanitized = re.sub(r'[<>:"/\\|?*]', '', original_filename)
    sanitized = re.sub(r'[.,]', '', sanitized)
    sanitized = re.sub(r'[\s-]+', '_', sanitized)
    sanitized = sanitized.strip('._- ')
    return sanitized.strip()


@retry_on_failure(max_retries=MAX_RETRIES, delay=RETRY_DELAY)
def download_file(url, file_path, current_page_url=None):
    """Realiza o download com barra de progresso e retry automático."""
    filename = os.path.basename(file_path)
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8'
    }
    if current_page_url:
        headers['Referer'] = current_page_url

    response = requests.get(url, stream=True, timeout=120, headers=headers)
    response.raise_for_status()

    total_size = int(response.headers.get('content-length', 0))

    if total_size and total_size < 1024:
        log_warning(f"Conteúdo suspeitamente pequeno ({total_size} bytes).")

    with open(file_path, 'wb') as f:
        with tqdm(total=total_size, unit='B', unit_scale=True, desc=filename[:40], ncols=80) as pbar:
            for chunk in response.iter_content(chunk_size=8192):
                f.write(chunk)
                pbar.update(len(chunk))

    log_success(f"Baixado: {filename}")
    return True


class DownloadManager:
    """Gerenciador de downloads paralelos em background."""

    def __init__(self, max_workers=MAX_PARALLEL_DOWNLOADS):
        self.executor = ThreadPoolExecutor(max_workers=max_workers)
        self.futures = []
        self.lock = threading.Lock()
        self.completed = 0
        self.failed = 0
        self.total = 0

    def add_download(self, url, file_path, referer=None):
        """Adiciona um download à fila de background."""
        if os.path.exists(file_path):
            return  # Já existe, não adiciona

        with self.lock:
            self.total += 1

        future = self.executor.submit(self._download_task, url, file_path, referer)
        self.futures.append((future, file_path))

    def _download_task(self, url, file_path, referer):
        """Tarefa de download executada em background."""
        try:
            download_file(url, file_path, referer)
            with self.lock:
                self.completed += 1
            return True
        except Exception as e:
            with self.lock:
                self.failed += 1
            return False

    def wait_all(self):
        """Aguarda todos os downloads em andamento."""
        if not self.futures:
            return

        log_info(f"Aguardando {len(self.futures)} downloads em background...")

        for future, file_path in self.futures:
            try:
                future.result(timeout=300)  # 5 min timeout por arquivo
            except Exception as e:
                log_error(f"Erro em download: {os.path.basename(file_path)}")

        with self.lock:
            if self.total > 0:
                log_success(f"Downloads concluídos: {self.completed}/{self.total} (falhas: {self.failed})")

        self.futures = []

    def shutdown(self):
        """Encerra o gerenciador de downloads."""
        self.wait_all()
        self.executor.shutdown(wait=True)


def handle_popups(sb):
    """Tenta fechar popups conhecidos."""
    try:
        if sb.is_element_present("#getsitecontrol-44266"):
            sb.execute_script('document.getElementById("getsitecontrol-44266").style.display = "none";')
            log_info("Popup detectado e escondido.")
            time.sleep(1)
    except Exception:
        pass


def get_course_data(sb):
    """Navega até 'Meus Cursos' e extrai os links e títulos."""
    log_info("Navegando para a página 'Meus Cursos'...")
    sb.open(MY_COURSES_URL)

    try:
        sb.wait_for_element("section[id^='card'] a.sc-cHGsZl", timeout=30)
        time.sleep(3)

        course_elements = sb.find_elements("section[id^='card']")
        courses = []
        for course_elem in course_elements:
            try:
                link_elem = course_elem.find_element("css selector", "a.sc-cHGsZl")
                title_elem = course_elem.find_element("css selector", "h1.sc-ksYbfQ")
                course_href = link_elem.get_attribute('href')
                course_title = title_elem.text
                if course_href and course_title:
                    courses.append({"title": course_title, "url": course_href})
            except Exception:
                pass
        log_success(f"Encontrados {len(courses)} cursos.")
        return courses
    except Exception as e:
        log_error(f"Erro ao carregar cursos: {e}")
        return []


def get_lesson_data(sb, course_url):
    """Extrai os links, títulos e subtítulos das aulas."""
    sb.open(course_url)

    try:
        sb.wait_for_element("div.LessonList-item a.Collapse-header", timeout=30)
        time.sleep(3)

        lesson_elements = sb.find_elements("div.LessonList-item")
        lessons = []
        for lesson_elem in lesson_elements:
            try:
                if "isDisabled" in (lesson_elem.get_attribute("class") or ""):
                    continue

                link_elem = lesson_elem.find_element("css selector", "a.Collapse-header")
                title_h2_elem = lesson_elem.find_element("css selector", "h2.SectionTitle")
                lesson_title = title_h2_elem.text

                lesson_subtitle = ""
                try:
                    title_p_elem = lesson_elem.find_element("css selector", "p.sc-gZMcBi")
                    lesson_subtitle = title_p_elem.text
                except Exception:
                    pass

                lesson_href = link_elem.get_attribute('href')
                if lesson_href and lesson_title:
                    lessons.append({
                        "title": lesson_title,
                        "subtitle": lesson_subtitle,
                        "url": lesson_href
                    })
            except Exception:
                pass
        log_info(f"Encontradas {len(lessons)} aulas disponíveis.")
        return lessons
    except Exception as e:
        log_error(f"Erro ao carregar aulas: {e}")
        return []


def download_lesson_materials(sb, lesson_info, course_title, download_dir, download_manager=None):
    """Navega para uma aula e baixa os materiais (com suporte a downloads em background)."""
    lesson_title = lesson_info['title']
    lesson_subtitle = lesson_info['subtitle']
    lesson_url = lesson_info['url']

    sb.open(lesson_url)

    try:
        sb.wait_for_element("div.Lesson-contentTop, div.LessonVideos", timeout=20)
        time.sleep(2)
    except Exception:
        log_error(f"Tempo esgotado ao carregar aula '{lesson_title}'.")
        return

    handle_popups(sb)

    sanitized_course_title = sanitize_filename(course_title)
    sanitized_lesson_title = sanitize_filename(lesson_title)
    lesson_download_path = os.path.join(download_dir, sanitized_course_title, sanitized_lesson_title)

    try:
        os.makedirs(lesson_download_path, exist_ok=True)
    except OSError as e:
        log_error(f"Erro ao criar diretório: {e}")
        return

    current_url = sb.get_current_url()

    # Função helper para adicionar downloads
    def queue_download(url, file_path):
        if download_manager:
            download_manager.add_download(url, file_path, current_url)
        elif not os.path.exists(file_path):
            try:
                download_file(url, file_path, current_url)
            except Exception as e:
                log_error(f"Erro no download: {e}")

    # Salva subtítulo
    if lesson_subtitle:
        subjects_file_path = os.path.join(lesson_download_path, "Assuntos_dessa_aula.txt")
        if not os.path.exists(subjects_file_path):
            try:
                with open(subjects_file_path, 'w', encoding='utf-8') as f:
                    f.write(lesson_subtitle)
            except Exception:
                pass

    # Baixa PDFs
    log_info("Procurando PDFs...")
    try:
        pdf_links = sb.find_elements("xpath", "//a[contains(@class, 'LessonButton') and .//i[contains(@class, 'icon-file')]]")
        for pdf_link in pdf_links:
            pdf_url = pdf_link.get_attribute('href')
            if not pdf_url or "api.estrategiaconcursos.com.br" not in pdf_url:
                continue

            pdf_text_raw = "original"
            try:
                version_text_element = pdf_link.find_element("css selector", "span.LessonButton-text > span")
                pdf_text_raw = version_text_element.text.strip()
            except Exception:
                pass

            filename = f"{sanitized_lesson_title}_Livro_Eletronico_{sanitize_filename(pdf_text_raw)}.pdf"
            full_file_path = os.path.join(lesson_download_path, filename)
            queue_download(pdf_url, full_file_path)
    except Exception:
        pass

    # Baixa Vídeos
    log_info("Procurando vídeos...")
    try:
        sb.wait_for_element("div.ListVideos-items-video a.VideoItem", timeout=10)
        playlist_items = sb.find_elements("div.ListVideos-items-video a.VideoItem")

        videos_to_download = []
        for item in playlist_items:
            video_href = item.get_attribute('href')
            video_title_elem = item.find_element("css selector", "span.VideoItem-info-title")
            video_title = video_title_elem.text
            if video_href and video_title:
                videos_to_download.append({'url': video_href, 'title': video_title})

        if not videos_to_download:
            log_info("Nenhum vídeo encontrado.")
            return

        log_success(f"Encontrados {len(videos_to_download)} vídeos.")

        for i, video_info in enumerate(tqdm(videos_to_download, desc="Vídeos", ncols=80, leave=False)):
            sb.open(video_info['url'])
            time.sleep(2)
            current_url = sb.get_current_url()

            # Baixar PDFs do vídeo
            video_pdf_types = {
                "Baixar Resumo": f"_Resumo_{i}.pdf",
                "Baixar Slides": f"_Slides_{i}.pdf",
                "Baixar Mapa Mental": f"_MapaMental_{i}.pdf"
            }

            for pdf_button_text, filename_suffix in video_pdf_types.items():
                try:
                    pdf_link_elem = sb.find_element("xpath", f"//a[contains(@class, 'LessonButton') and .//span[contains(text(), '{pdf_button_text}')]]")
                    pdf_url = pdf_link_elem.get_attribute('href')

                    if pdf_url:
                        filename = f"{sanitized_lesson_title}_{sanitize_filename(video_info['title'])}{filename_suffix}"
                        full_file_path = os.path.join(lesson_download_path, filename)
                        queue_download(pdf_url, full_file_path)
                except Exception:
                    pass

            # Baixar vídeo
            try:
                sb.wait_for_element("xpath", "//div[contains(@class, 'Collapse-header')]//strong[text()='Opções de download']", timeout=10)
                download_header = sb.find_element("xpath", "//div[contains(@class, 'Collapse-header')]//strong[text()='Opções de download']")

                header_container = download_header.find_element("xpath", "./ancestor::div[contains(@class, 'Collapse-header-container')]")
                collapse_body = header_container.find_element("xpath", "./following-sibling::div")

                if not collapse_body.is_displayed():
                    sb.execute_script("arguments[0].click();", download_header)
                    time.sleep(1)

                sanitized_video_title = sanitize_filename(video_info['title'])

                for quality in ["720p", "480p", "360p"]:
                    filename = f"{sanitized_video_title}_Video_{quality}.mp4"
                    full_file_path = os.path.join(lesson_download_path, filename)

                    if os.path.exists(full_file_path):
                        break

                    try:
                        video_link_elem = collapse_body.find_element("xpath", f".//a[contains(text(), '{quality}')]")
                        video_url = video_link_elem.get_attribute('href')
                        queue_download(video_url, full_file_path)
                        break
                    except Exception:
                        continue

            except Exception:
                pass

    except Exception:
        log_info("Nenhuma playlist de vídeos encontrada.")


# --- Login ---
def login(sb, wait_time, headless):
    """Pausa para login manual."""
    log_info("Navegando para a página de login...")
    sb.open("https://perfil.estrategia.com/login")

    if headless:
        log_error("MODO HEADLESS: Login manual não suportado. Execute sem --headless.")
        sys.exit(1)

    log_header("AÇÃO NECESSÁRIA: FAÇA O LOGIN MANUALMENTE")
    print(f"{Fore.YELLOW}O script aguardará {wait_time} segundos para você completar o login.")
    print(f"NÃO feche o navegador.{Style.RESET_ALL}")

    time.sleep(wait_time)
    log_success("Login concluído. Continuando...")


# --- Sistema de Progresso ---
def get_progress_file_path(download_dir):
    return os.path.join(download_dir, ".progress.json")


def load_progress(download_dir):
    progress_file = get_progress_file_path(download_dir)
    if os.path.exists(progress_file):
        try:
            with open(progress_file, 'r', encoding='utf-8') as f:
                progress = json.load(f)
                log_info(f"Progresso carregado: Curso {progress.get('course_index', 0) + 1}, Aula {progress.get('lesson_index', 0) + 1}")
                return progress
        except Exception:
            pass
    return {"course_index": 0, "lesson_index": 0, "completed_lessons": []}


def save_progress(download_dir, course_index, lesson_index, completed_lessons):
    progress_file = get_progress_file_path(download_dir)
    try:
        with open(progress_file, 'w', encoding='utf-8') as f:
            json.dump({
                "course_index": course_index,
                "lesson_index": lesson_index,
                "completed_lessons": completed_lessons
            }, f, ensure_ascii=False, indent=2)
    except Exception:
        pass


def is_lesson_completed(completed_lessons, course_title, lesson_title):
    return f"{course_title}::{lesson_title}" in completed_lessons


def mark_lesson_completed(completed_lessons, course_title, lesson_title):
    key = f"{course_title}::{lesson_title}"
    if key not in completed_lessons:
        completed_lessons.append(key)


# --- Fluxo Principal ---
def run_downloader(download_dir, login_wait_time, reset_progress=False, headless=False, parallel=True):
    try:
        os.makedirs(download_dir, exist_ok=True)
        log_success(f"Diretório: {os.path.abspath(download_dir)}")
    except OSError as e:
        log_error(f"Não foi possível criar diretório: {e}")
        sys.exit(1)

    if reset_progress:
        progress = {"course_index": 0, "lesson_index": 0, "completed_lessons": []}
        log_info("Progresso resetado.")
    else:
        progress = load_progress(download_dir)

    start_course = progress.get("course_index", 0)
    start_lesson = progress.get("lesson_index", 0)
    completed_lessons = progress.get("completed_lessons", [])

    # Cria gerenciador de downloads paralelos
    download_manager = DownloadManager() if parallel else None
    if parallel:
        log_info(f"Downloads paralelos ativados ({MAX_PARALLEL_DOWNLOADS} simultâneos)")

    with SB(uc=True, headless=headless, locale_code="pt-BR") as sb:
        try:
            login(sb, login_wait_time, headless)

            courses = get_course_data(sb)
            if not courses:
                log_error("Nenhum curso encontrado.")
                return

            for i, course in enumerate(tqdm(courses, desc="Cursos", ncols=80)):
                if i < start_course:
                    continue

                log_header(f"[{i + 1}/{len(courses)}] {course['title']}")
                lessons = get_lesson_data(sb, course['url'])

                if not lessons:
                    log_warning("Nenhuma aula encontrada.")
                    continue

                for j, lesson_info in enumerate(lessons):
                    if i == start_course and j < start_lesson:
                        continue

                    if is_lesson_completed(completed_lessons, course['title'], lesson_info['title']):
                        continue

                    log_info(f"[{j + 1}/{len(lessons)}] {lesson_info['title']}")
                    download_lesson_materials(sb, lesson_info, course['title'], download_dir, download_manager)

                    mark_lesson_completed(completed_lessons, course['title'], lesson_info['title'])
                    save_progress(download_dir, i, j + 1, completed_lessons)

                    # Aguarda downloads pendentes periodicamente
                    if download_manager and download_manager.total > 0 and j % 5 == 0:
                        download_manager.wait_all()

                    time.sleep(2)

                start_lesson = 0

                # Aguarda downloads ao final de cada curso
                if download_manager:
                    download_manager.wait_all()

        except KeyboardInterrupt:
            log_warning("\nInterrompido pelo usuário. Progresso salvo.")
        except Exception as e:
            log_error(f"Erro: {e}")
            log_info("Progresso salvo. Execute novamente para retomar.")
        finally:
            # Aguarda downloads restantes
            if download_manager:
                download_manager.shutdown()

    log_success("Processo concluído!")


def main():
    parser = argparse.ArgumentParser(
        description="Baixador de cursos do Estratégia Concursos com anti-detecção.",
        formatter_class=argparse.RawTextHelpFormatter
    )

    parser.add_argument(
        '-d', '--dir',
        dest='download_dir',
        metavar='PATH',
        type=str,
        default=os.path.expanduser("~/Downloads/Estrategia"),
        help="Diretório de download (padrão: ~/Downloads/Estrategia)"
    )

    parser.add_argument(
        "-w", "--wait-time",
        type=int,
        default=60,
        help="Tempo para login manual em segundos (padrão: 60)"
    )

    parser.add_argument(
        "-r", "--reset",
        action="store_true",
        help="Ignora progresso salvo e recomeça"
    )

    parser.add_argument(
        "--headless",
        action="store_true",
        help="Executa sem interface gráfica"
    )

    parser.add_argument(
        "--no-parallel",
        action="store_true",
        help="Desativa downloads paralelos (sequencial)"
    )

    args = parser.parse_args()
    run_downloader(args.download_dir, args.wait_time, args.reset, args.headless, not args.no_parallel)


if __name__ == "__main__":
    main()
