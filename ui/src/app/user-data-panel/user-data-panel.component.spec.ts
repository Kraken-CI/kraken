import { ComponentFixture, TestBed } from '@angular/core/testing';

import { UserDataPanelComponent } from './user-data-panel.component';

describe('UserDataPanelComponent', () => {
  let component: UserDataPanelComponent;
  let fixture: ComponentFixture<UserDataPanelComponent>;

  beforeEach(async () => {
    await TestBed.configureTestingModule({
      declarations: [ UserDataPanelComponent ]
    })
    .compileComponents();

    fixture = TestBed.createComponent(UserDataPanelComponent);
    component = fixture.componentInstance;
    fixture.detectChanges();
  });

  it('should create', () => {
    expect(component).toBeTruthy();
  });
});
