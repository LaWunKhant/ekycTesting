<?php

use App\Models\User;

test('guests are redirected from home to login', function () {
    $response = $this->get('/');

    $response->assertRedirect('/login');
});

test('authenticated users are redirected from home to the dashboard', function () {
    $user = new User([
        'email' => 'test@example.com',
        'password' => 'password',
    ]);

    $this->actingAs($user);

    $response = $this->get('/');

    $response->assertRedirect('/dashboard');
});
