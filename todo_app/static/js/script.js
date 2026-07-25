// Confirm before permanently deleting a task
document.addEventListener("DOMContentLoaded", function () {
    const deleteButtons = document.querySelectorAll(".confirm-delete");

    deleteButtons.forEach(function (button) {
        button.addEventListener("click", function (event) {
            const confirmed = confirm("Are you sure you want to delete this task? This cannot be undone.");
            if (!confirmed) {
                event.preventDefault();
            }
        });
    });

    // Auto-hide flash messages after 4 seconds
    const flashMessages = document.querySelectorAll(".flash");
    flashMessages.forEach(function (msg) {
        setTimeout(function () {
            msg.style.transition = "opacity 0.4s ease";
            msg.style.opacity = "0";
            setTimeout(function () {
                msg.remove();
            }, 400);
        }, 4000);
    });
});
