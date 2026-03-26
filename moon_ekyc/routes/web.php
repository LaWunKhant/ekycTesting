<?php

use App\Http\Controllers\TenantDashboardController;
use App\Http\Controllers\TenantReviewController;
use App\Http\Controllers\TenantSessionsController;
use App\Http\Controllers\TenantTeamController;
use App\Models\Tenant;
use Illuminate\Http\Request;
use Illuminate\Support\Facades\Auth;
use Illuminate\Support\Facades\Route;

Route::get('/', function (Request $request) {
    if (Auth::check()) {
        return redirect()->route('dashboard');
    }

    return redirect()->route('login');
})->name('home');

Route::middleware(['auth'])->group(function () {
    Route::get('dashboard', [TenantDashboardController::class, 'show'])->name('dashboard');
    Route::post('dashboard', [TenantDashboardController::class, 'store'])->name('dashboard.store');

    Route::get('sessions', [TenantSessionsController::class, 'index'])->name('sessions.index');

    Route::get('team', [TenantTeamController::class, 'index'])->name('team.index');

    Route::get('review', [TenantReviewController::class, 'index'])->name('review.index');
});

require __DIR__.'/settings.php';
require __DIR__.'/auth.php';
