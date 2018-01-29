<template id="crm" type="text/html">
    <section id='crm'>
        <section class='header clearfix crm_menu'>
            <ul class='clearfix menu'>
                <li data-route='messages'>Сообщения</li>
                <li data-route='tasks'>Задачи</li>
                <li data-route='leads'>Лиды</li>
            </ul>
            <input class='search' placeholder='Начните вводить id, имя или сообщение' tabindex='-1' data-page='message_list'>
            <ul class='filter' data-page='message_list'>
                <li >Все сообщения</li>
                <li>Входящие</li>
                <li>Исходящие</li>
            </ul>
            <ul class='filter task_switch' data-page='tasks'>
                <li callback='Tasks.Week.init();'>Задачи за неделю</li>
                <li callback='Tasks.Month.init();'>Задачи за месяц</li>
                <li callback='Tasks.Day.init();'>Задачи за день</li>
            </ul>
            <ul class='filter task_filter' data-page='tasks'>
                <li>Все задачи</li>
                <li>Активные</li>
            </ul>
        </section>
        <section id='crm_panel'>

        </section>
    </section>
</template>

<template id="object_tooltip">
    <section id="object_tooltip" class="clearfix tooltip">
        <figure style="background-image: url(img/common/room_1.jpg);"></figure>
        <article>
            <h1>Вишневая, 10</h1>
            <h2>
                Продажа, квартира
                <span>774335</span>
            </h2>
            <p>Отдел продаж</p>
            <p>+38 (096) 900-90-08</p>
        </article>
    </section>
</template>