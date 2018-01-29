Порядок развертывания локальной копии проекта
=============================================

1. запустить **git clone https://bitbucket.org/z268/mesto**
2. перейти в директорию проекта
3. создать папку *.buildout*
4. создать файл *buildout.cfg*, содержащий

        [buildout]
        extends = buildout_base.cfg

5. установить buildout **pip install zc.buildout**
6. запустить **buildout install**
7. установить библиотеки для работы GeoDjango: https://docs.djangoproject.com/en/1.9/ref/contrib/gis/install/
8. настроить основной локальный домен и его поддомены в */etc/hosts*, например,

        127.0.0.1 mesto.loc
        127.0.0.1 kiev.mesto.loc
        127.0.0.1 bank.mesto.loc
        127.0.0.1 bank.kiev.mesto.loc

9. развернуть БД из дампа
10. в БД исправить домен сайта на локальный в таблице `django_site` (см. пункт 8)
11. скопировать *_site/settings_local_sample.py* в *_site/settings_local.py*, настроить в нем доступ к БД и в переменной `SESSION_COOKIE_DOMAIN` указать локальный домен (см. пункт 8)
12. для запуска сайта выполнить **.buildout/bin/django runserver**

FAQ
===

Q: Не получается авторизоватся на сайте  
A: Скорее всего, проблема с переменной `SESSION_COOKIE_DOMAIN`, она должна соответствовать домену с которого открывается сайт
