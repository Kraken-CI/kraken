import { ComponentFixture, TestBed } from '@angular/core/testing';

import { SimpleLogsPanelComponent } from './simple-logs-panel.component';

describe('SimpleLogsPanelComponent', () => {
  let component: SimpleLogsPanelComponent;
  let fixture: ComponentFixture<SimpleLogsPanelComponent>;

  beforeEach(async () => {
    await TestBed.configureTestingModule({
      declarations: [ SimpleLogsPanelComponent ]
    })
    .compileComponents();

    fixture = TestBed.createComponent(SimpleLogsPanelComponent);
    component = fixture.componentInstance;
    fixture.detectChanges();
  });

  it('should create', () => {
    expect(component).toBeTruthy();
  });
});
