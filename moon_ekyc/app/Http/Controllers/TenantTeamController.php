<?php

namespace App\Http\Controllers;

use Illuminate\Http\Request;
use Inertia\Inertia;
use Inertia\Response;

class TenantTeamController extends Controller
{
    public function index(Request $request): Response
    {
        return Inertia::render('Tenant/Team', [
            'staff' => [
                [
                    'email' => $request->user()?->email ?? 'owner@example.com',
                    'role' => 'owner',
                ],
            ],
        ]);
    }
}
